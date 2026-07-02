import logging

from fastapi import APIRouter, HTTPException

from bundesrag.i18n import t
from bundesrag.ingestion.pipeline import run_delete_all, run_status
from bundesrag.logging_config import LOGGER_NAME
from bundesrag.rag.answer_agent import answer_question
from bundesrag.web.dependencies import ChatLlmDep, SettingsDep, VectorstoreDep
from bundesrag.web.schemas import (
    AskRequest,
    AskResponse,
    ClearRequest,
    DeleteSummaryResponse,
    FileStatusResponse,
    StatusResponse,
)

router = APIRouter()

logger = logging.getLogger(LOGGER_NAME)


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
    return AskResponse(answer_text=result.answer_text, sources=result.sources)


@router.post("/clear", response_model=DeleteSummaryResponse)
def clear(
    request: ClearRequest,
    settings: SettingsDep,
    vectorstore: VectorstoreDep,
) -> DeleteSummaryResponse:
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="confirmation required")
    logger.info("web clear invoked")
    try:
        summary = run_delete_all(settings, vectorstore=vectorstore)
    except Exception:
        logger.exception("web clear failed")
        raise HTTPException(status_code=500, detail=t("unexpected_error")) from None
    return DeleteSummaryResponse(num_files=summary.num_files)


@router.get("/status", response_model=StatusResponse)
def status(settings: SettingsDep) -> StatusResponse:
    summary = run_status(settings)
    return StatusResponse(
        num_downloaded=summary.num_downloaded,
        num_indexed=summary.num_indexed,
        files=[
            FileStatusResponse(pdf_path=str(file.pdf_path), indexed=file.indexed)
            for file in summary.files
        ],
    )
