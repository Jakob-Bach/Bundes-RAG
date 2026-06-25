import typer

from bundesrag.config import Settings
from bundesrag.dip.client import DipClient
from bundesrag.i18n import set_language, t
from bundesrag.ingestion.pipeline import (
    DownloadAborted,
    run_delete_all,
    run_download,
    run_index,
)
from bundesrag.query_agent.agent import create_query_agent, format_filters
from bundesrag.query_agent.schema import DipQueryFilters
from bundesrag.rag.answer_agent import answer_question, create_chat_llm
from bundesrag.vectorstore import get_vectorstore

app = typer.Typer(help="Download Bundestag documents and ask questions about them.")


def _confirm_filters(filters: DipQueryFilters) -> bool:
    typer.echo(format_filters(filters))
    return typer.confirm(t("confirm_use_query"))


@app.command()
def download(prompt: str) -> None:
    """Downloads documents matching PROMPT, without indexing them."""
    settings = Settings()
    set_language(settings.language)
    dip_client = DipClient(api_key=settings.dip_api_key)
    try:
        summary = run_download(
            prompt,
            settings,
            query_agent=create_query_agent(settings),
            dip_client=dip_client,
            ask_user=typer.prompt,
            confirm=typer.confirm,
            confirm_filters=_confirm_filters,
        )
    except DownloadAborted as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    finally:
        dip_client.close()
    typer.echo(t("download_done", num_documents=summary.num_documents))


@app.command()
def index() -> None:
    """Indexes previously downloaded but not yet indexed documents."""
    settings = Settings()
    set_language(settings.language)
    summary = run_index(settings, vectorstore=get_vectorstore(settings))
    typer.echo(t("index_done", num_documents=summary.num_documents, num_chunks=summary.num_chunks))


@app.command()
def clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="Delete without asking for confirmation."),
) -> None:
    """Deletes all downloaded documents and resets the vector store."""
    settings = Settings()
    set_language(settings.language)
    if not yes and not typer.confirm(t("confirm_delete_all")):
        raise typer.Exit(code=1)
    summary = run_delete_all(settings, vectorstore=get_vectorstore(settings))
    typer.echo(t("delete_done", num_files=summary.num_files))


@app.command()
def ask(question: str) -> None:
    """Answers QUESTION based on the stored documents."""
    settings = Settings()
    set_language(settings.language)
    result = answer_question(
        question,
        settings,
        llm=create_chat_llm(settings),
        vectorstore=get_vectorstore(settings),
    )
    typer.echo(result.answer_text)
    typer.echo(t("sources_header"))
    for source in result.sources:
        typer.echo(f"  - {source}")


if __name__ == "__main__":
    app()
