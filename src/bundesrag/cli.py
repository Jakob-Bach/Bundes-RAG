import logging

import typer

from bundesrag.config import Settings
from bundesrag.dip.client import DipClient
from bundesrag.i18n import set_language, t, yes_no_tokens
from bundesrag.ingestion.pipeline import (
    DownloadAborted,
    run_delete_all,
    run_download,
    run_index,
    run_status,
)
from bundesrag.logging_config import LOGGER_NAME, setup_logging
from bundesrag.query_agent.agent import create_query_agent, format_filters
from bundesrag.query_agent.schema import DipQueryFilters
from bundesrag.rag.answer_agent import answer_question, create_chat_llm
from bundesrag.vectorstore import get_vectorstore

app = typer.Typer(help="Download Bundestag documents and ask questions about them.")

logger = logging.getLogger(LOGGER_NAME)


def _init() -> Settings:
    settings = Settings()
    set_language(settings.language)
    setup_logging(settings)
    return settings


def _confirm(text: str) -> bool:
    """Asks a yes/no question, accepting answers in the current language.

    typer.confirm() only ever recognizes English y/yes/n/no, which silently
    rejects a German "j" answer to a localized "[j/N]" prompt.
    """
    yes_tokens, no_tokens = yes_no_tokens()
    while True:
        answer = typer.prompt(text, default="", show_default=False, prompt_suffix="")
        answer = answer.strip().lower()
        if not answer or answer in no_tokens:
            return False
        if answer in yes_tokens:
            return True


def _confirm_filters(filters: DipQueryFilters) -> bool:
    typer.echo(format_filters(filters))
    return _confirm(t("confirm_use_query_yn"))


def _confirm_count(count: int) -> int:
    raw = typer.prompt(t("ask_download_count", count=count), default=str(count))
    try:
        chosen = int(raw)
    except ValueError:
        return count
    return max(0, min(chosen, count))


@app.command()
def download(prompt: str) -> None:
    """Downloads documents matching PROMPT, without indexing them.

    PROMPT is a natural-language description of the documents to fetch. An LLM
    translates it into DIP API filters and asks for clarification if the prompt
    is too vague.

    Available endpoints:

    \b
    - drucksache: Anträge, Gesetzentwürfe, Kleine Anfragen, etc.
    - plenarprotokoll: Plenarsitzungsprotokolle.

    Available filters (all optional):

    \b
    - datum_start / datum_end: Datumsbereich (z. B. "seit 01.01.2026")
    - wahlperiode: Wahlperiodennummer (z. B. 21)
    - dokumentnummer: exakte Drucksachen-/Protokollnummer (z. B. "19/1")
    - zuordnung: BT, BR, BV oder EK
    - drucksachetyp: Dokumenttyp, z. B. "Antrag", "Gesetzentwurf" (nur drucksache)
    - urheber: Urheber/Fraktion, z. B. "Fraktion der SPD" (nur drucksache)
    - ressort_fdf: federführendes Bundesministerium (nur drucksache)
    - titel: Suchbegriffe im Titel, ODER-verknüpft (nur drucksache)

    Note: urheber and ressort_fdf use AND logic across multiple values. To find
    documents from either of two authors, run separate download commands.
    """
    settings = _init()
    logger.info("download query: %s", prompt)
    dip_client = DipClient(api_key=settings.dip_api_key)
    try:
        summary = run_download(
            prompt,
            settings,
            query_agent=create_query_agent(settings),
            dip_client=dip_client,
            ask_user=typer.prompt,
            confirm_count=_confirm_count,
            confirm_filters=_confirm_filters,
        )
    except DownloadAborted as exc:
        logger.warning("download aborted: %s", exc)
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    except Exception:
        logger.exception("download failed")
        typer.echo(t("unexpected_error"))
        raise typer.Exit(code=1) from None
    finally:
        dip_client.close()
    logger.info(
        "download succeeded: %d documents, %d failed", summary.num_documents, summary.num_failed
    )
    typer.echo(t("download_done", num_documents=summary.num_documents))
    if summary.num_failed:
        typer.echo(t("download_partial_failure", num_failed=summary.num_failed))


@app.command()
def index() -> None:
    """Indexes previously downloaded but not yet indexed documents."""
    settings = _init()
    logger.info("index command invoked")
    try:
        summary = run_index(settings, vectorstore=get_vectorstore(settings))
    except Exception:
        logger.exception("index failed")
        typer.echo(t("unexpected_error"))
        raise typer.Exit(code=1) from None
    logger.info(
        "index succeeded: %d documents, %d chunks", summary.num_documents, summary.num_chunks
    )
    typer.echo(t("index_done", num_documents=summary.num_documents, num_chunks=summary.num_chunks))


@app.command()
def clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="Delete without asking for confirmation."),
) -> None:
    """Deletes all downloaded documents and resets the vector store."""
    settings = _init()
    logger.info("clear command invoked")
    if not yes and not _confirm(t("confirm_delete_all_yn")):
        logger.warning("clear aborted: user declined confirmation")
        raise typer.Exit(code=1)
    try:
        summary = run_delete_all(settings, vectorstore=get_vectorstore(settings))
    except Exception:
        logger.exception("clear failed")
        typer.echo(t("unexpected_error"))
        raise typer.Exit(code=1) from None
    logger.info("clear succeeded: %d files deleted", summary.num_files)
    typer.echo(t("delete_done", num_files=summary.num_files))


@app.command()
def status() -> None:
    """Shows how many documents are downloaded and indexed."""
    settings = _init()
    logger.info("status command invoked")
    summary = run_status(settings)
    logger.info(
        "status succeeded: %d downloaded, %d indexed",
        summary.num_downloaded,
        summary.num_indexed,
    )
    typer.echo(t("status_num_downloaded", count=summary.num_downloaded))
    typer.echo(t("status_num_indexed", count=summary.num_indexed))
    typer.echo(t("status_files_header"))
    for file in summary.files:
        status_label = t("status_file_indexed") if file.indexed else t("status_file_not_indexed")
        typer.echo(f"  - {file.pdf_path} ({status_label})")


@app.command()
def ask(question: str) -> None:
    """Answers QUESTION based on the stored documents."""
    settings = _init()
    logger.info("ask query: %s", question)
    try:
        result = answer_question(
            question,
            settings,
            llm=create_chat_llm(settings),
            vectorstore=get_vectorstore(settings),
        )
    except Exception:
        logger.exception("ask failed")
        typer.echo(t("unexpected_error"))
        raise typer.Exit(code=1) from None
    logger.info("ask succeeded: %d sources", len(result.sources))
    typer.echo(result.answer_text)
    typer.echo(t("sources_header"))
    for source in result.sources:
        typer.echo(f"  - {source}")


if __name__ == "__main__":
    app()
