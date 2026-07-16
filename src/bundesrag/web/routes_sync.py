import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from bundesrag.i18n import t
from bundesrag.ingestion.pipeline import run_delete_all, run_delete_file, run_status
from bundesrag.logging_config import LOGGER_NAME
from bundesrag.rag.answer_agent import answer_question
from bundesrag.web.dependencies import (
    ChatLlmDep,
    MetadataVectorstoreDep,
    SettingsDep,
    VectorstoreDep,
)
from bundesrag.web.schemas import (
    AskRequest,
    AskResponse,
    ClearRequest,
    ConfigResponse,
    DeleteFileRequest,
    DeleteSummaryResponse,
    DocumentInfoResponse,
    FileStatusResponse,
    StatusResponse,
)

router = APIRouter()

logger = logging.getLogger(LOGGER_NAME)


@router.get("/config", response_model=ConfigResponse)
def get_config(settings: SettingsDep) -> ConfigResponse:
    return ConfigResponse(language=settings.language)


@router.post("/ask", response_model=AskResponse)
def ask(
    request: AskRequest,
    settings: SettingsDep,
    llm: ChatLlmDep,
    vectorstore: VectorstoreDep,
) -> AskResponse:
    logger.info("web ask query: %s", request.question)
    try:
        result = answer_question(request.question, settings, llm=llm, vectorstore=vectorstore)
    except Exception:
        logger.exception("web ask failed")
        raise HTTPException(status_code=500, detail=t("unexpected_error")) from None
    logger.info("web ask succeeded: %d sources", len(result.sources))
    return AskResponse(answer_text=result.answer_text, sources=result.sources)


@router.post("/clear", response_model=DeleteSummaryResponse)
def clear(
    request: ClearRequest,
    settings: SettingsDep,
    vectorstore: MetadataVectorstoreDep,
) -> DeleteSummaryResponse:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail=t("confirmation_required"))
    logger.info("web clear invoked")
    try:
        summary = run_delete_all(settings, vectorstore=vectorstore)
    except Exception:
        logger.exception("web clear failed")
        raise HTTPException(status_code=500, detail=t("unexpected_error")) from None
    logger.info("web clear succeeded: %d files deleted", summary.num_files)
    return DeleteSummaryResponse(num_files=summary.num_files)


@router.post("/files/delete", status_code=204)
def delete_file(
    request: DeleteFileRequest,
    settings: SettingsDep,
    vectorstore: MetadataVectorstoreDep,
) -> None:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail=t("confirmation_required"))
    logger.info("web delete file invoked: %s", request.pdf_path)
    try:
        run_delete_file(Path(request.pdf_path), settings, vectorstore=vectorstore)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=t("file_not_found")) from None
    except Exception:
        logger.exception("web delete file failed")
        raise HTTPException(status_code=500, detail=t("unexpected_error")) from None
    logger.info("web delete file succeeded: %s", request.pdf_path)


@router.get("/status", response_model=StatusResponse)
def status(settings: SettingsDep, vectorstore: MetadataVectorstoreDep) -> StatusResponse:
    logger.info("web status invoked")
    try:
        summary = run_status(settings, vectorstore=vectorstore)
    except Exception:
        logger.exception("web status failed")
        raise HTTPException(status_code=500, detail=t("unexpected_error")) from None
    logger.info(
        "web status succeeded: %d downloaded, %d indexed, %d chunks",
        summary.num_downloaded,
        summary.num_indexed,
        summary.num_chunks,
    )
    return StatusResponse(
        num_downloaded=summary.num_downloaded,
        num_indexed=summary.num_indexed,
        num_chunks=summary.num_chunks,
        num_manifest_chunks=summary.num_manifest_chunks,
        pdf_size_bytes=summary.pdf_size_bytes,
        vectorstore_size_bytes=summary.vectorstore_size_bytes,
        files=[
            FileStatusResponse(
                pdf_path=str(file.pdf_path),
                indexed=file.indexed,
                kind=file.kind,
                info=(
                    DocumentInfoResponse(
                        doc_id=file.info.doc_id,
                        dokumentnummer=file.info.dokumentnummer,
                        citation_label=file.info.citation_label,
                        datum=file.info.datum,
                        source_url=file.info.source_url,
                        num_chunks=file.info.num_chunks,
                        num_pages=file.info.num_pages,
                    )
                    if file.info
                    else None
                ),
            )
            for file in summary.files
        ],
    )
