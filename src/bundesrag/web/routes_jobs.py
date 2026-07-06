import logging

from fastapi import APIRouter, HTTPException

from bundesrag.i18n import t
from bundesrag.ingestion.pipeline import (
    DownloadAborted,
    DownloadSummary,
    IndexSummary,
    OperationCancelled,
    run_download,
    run_index,
)
from bundesrag.logging_config import LOGGER_NAME
from bundesrag.query_agent.agent import format_filters
from bundesrag.query_agent.schema import DipQueryFilters
from bundesrag.web.dependencies import (
    DipClientDep,
    JobManagerDep,
    QueryAgentDep,
    SettingsDep,
    VectorstoreDep,
)
from bundesrag.web.jobs import (
    Job,
    JobManager,
    JobNotCancellableError,
    JobNotFoundError,
    JobNotWaitingError,
)
from bundesrag.web.schemas import (
    DownloadRequest,
    DownloadSummaryResponse,
    IndexSummaryResponse,
    JobResponse,
    PendingInputResponse,
    RespondRequest,
)

router = APIRouter()

logger = logging.getLogger(LOGGER_NAME)


def _job_response(job: Job) -> JobResponse:
    result = None
    if isinstance(job.result, DownloadSummary):
        result = DownloadSummaryResponse(
            num_documents=job.result.num_documents,
            num_failed=job.result.num_failed,
            num_skipped=job.result.num_skipped,
        )
    elif isinstance(job.result, IndexSummary):
        result = IndexSummaryResponse(
            num_documents=job.result.num_documents, num_chunks=job.result.num_chunks
        )
    return JobResponse(
        id=job.id,
        status=job.status,
        pending=job.pending,
        progress=job.progress,
        result=result,
        error=job.error,
    )


def _get_job_or_404(job_manager: JobManager, job_id: str) -> Job:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=t("job_not_found"))
    return job


def _cancel_job(job_manager: JobManager, job_id: str) -> None:
    try:
        job_manager.request_cancel(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=t("job_not_found")) from None
    except JobNotCancellableError:
        raise HTTPException(status_code=409, detail=t("job_not_cancellable")) from None


def _build_download_callables(job_manager: JobManager, job: Job):
    def ask_user(question: str) -> str:
        return job_manager.wait_for_answer(
            job, PendingInputResponse(kind="ask_user", question=question)
        )

    def confirm_filters(filters: DipQueryFilters) -> bool:
        answer = job_manager.wait_for_answer(
            job, PendingInputResponse(kind="confirm_filters", filters_text=format_filters(filters))
        )
        return answer.strip().lower() == "true"

    def confirm_count(count: int) -> int:
        answer = job_manager.wait_for_answer(
            job, PendingInputResponse(kind="confirm_count", count=count)
        )
        try:
            chosen = int(answer)
        except ValueError:
            return count
        return max(0, min(chosen, count))

    return ask_user, confirm_filters, confirm_count


@router.post("/download", response_model=JobResponse, status_code=202)
def start_download(
    request: DownloadRequest,
    settings: SettingsDep,
    job_manager: JobManagerDep,
    query_agent: QueryAgentDep,
    dip_client: DipClientDep,
) -> JobResponse:
    logger.info("web download query: %s", request.prompt)
    job = job_manager.create_job()
    ask_user, confirm_filters, confirm_count = _build_download_callables(job_manager, job)

    def target() -> DownloadSummary:
        try:
            summary = run_download(
                request.prompt,
                settings,
                query_agent=query_agent,
                dip_client=dip_client,
                ask_user=ask_user,
                confirm_count=confirm_count,
                confirm_filters=confirm_filters,
                on_progress=lambda current, total: job_manager.set_progress(job, current, total),
                should_cancel=lambda: job_manager.cancel_requested(job),
            )
        except OperationCancelled:
            logger.warning("web download cancelled")
            raise
        except DownloadAborted as exc:
            logger.warning("web download aborted: %s", exc)
            raise
        except Exception:
            logger.exception("web download failed")
            raise
        finally:
            dip_client.close()
        logger.info(
            "web download succeeded: %d documents, %d failed, %d already downloaded",
            summary.num_documents,
            summary.num_failed,
            summary.num_skipped,
        )
        return summary

    job_manager.run_in_background(job, target)
    return _job_response(job)


@router.get("/download/{job_id}", response_model=JobResponse)
def get_download_job(job_id: str, job_manager: JobManagerDep) -> JobResponse:
    return _job_response(_get_job_or_404(job_manager, job_id))


@router.post("/download/{job_id}/respond", status_code=204)
def respond_to_download_job(
    job_id: str,
    request: RespondRequest,
    job_manager: JobManagerDep,
) -> None:
    job = _get_job_or_404(job_manager, job_id)
    if job.pending is not None and job.pending.kind == "confirm_count":
        try:
            int(request.answer)
        except ValueError:
            raise HTTPException(status_code=400, detail=t("answer_must_be_integer")) from None
    try:
        job_manager.provide_answer(job_id, request.answer)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=t("job_not_found")) from None
    except JobNotWaitingError:
        raise HTTPException(status_code=409, detail=t("job_not_waiting")) from None


@router.post("/download/{job_id}/cancel", status_code=204)
def cancel_download_job(job_id: str, job_manager: JobManagerDep) -> None:
    _cancel_job(job_manager, job_id)


@router.post("/index", response_model=JobResponse, status_code=202)
def start_index(
    settings: SettingsDep,
    job_manager: JobManagerDep,
    vectorstore: VectorstoreDep,
) -> JobResponse:
    logger.info("web index invoked")
    job = job_manager.create_job()

    def target() -> IndexSummary:
        try:
            summary = run_index(
                settings,
                vectorstore=vectorstore,
                on_progress=lambda current, total: job_manager.set_progress(job, current, total),
                should_cancel=lambda: job_manager.cancel_requested(job),
            )
        except OperationCancelled:
            logger.warning("web index cancelled")
            raise
        except Exception:
            logger.exception("web index failed")
            raise
        logger.info(
            "web index succeeded: %d documents, %d chunks",
            summary.num_documents,
            summary.num_chunks,
        )
        return summary

    job_manager.run_in_background(job, target)
    return _job_response(job)


@router.get("/index/{job_id}", response_model=JobResponse)
def get_index_job(job_id: str, job_manager: JobManagerDep) -> JobResponse:
    return _job_response(_get_job_or_404(job_manager, job_id))


@router.post("/index/{job_id}/cancel", status_code=204)
def cancel_index_job(job_id: str, job_manager: JobManagerDep) -> None:
    _cancel_job(job_manager, job_id)
