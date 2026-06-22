import typer

from bundesrag.config import Settings
from bundesrag.dip.client import DipClient
from bundesrag.ingestion.pipeline import DownloadAborted, run_download, run_index
from bundesrag.query_agent.agent import create_query_agent
from bundesrag.rag.answer_agent import answer_question, create_chat_llm
from bundesrag.vectorstore import get_vectorstore

app = typer.Typer(help="Lade Bundestagsdokumente herunter und stelle Fragen dazu.")


@app.command()
def download(prompt: str) -> None:
    """Lädt Dokumente passend zu PROMPT herunter, ohne sie zu indexieren."""
    settings = Settings()
    dip_client = DipClient(api_key=settings.dip_api_key)
    try:
        summary = run_download(
            prompt,
            settings,
            query_agent=create_query_agent(settings),
            dip_client=dip_client,
            ask_user=typer.prompt,
            confirm=typer.confirm,
        )
    except DownloadAborted as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    finally:
        dip_client.close()
    typer.echo(f"Fertig: {summary.num_documents} Dokumente heruntergeladen.")


@app.command()
def index() -> None:
    """Indexiert zuvor heruntergeladene, aber noch nicht indexierte Dokumente."""
    settings = Settings()
    summary = run_index(settings, vectorstore=get_vectorstore(settings))
    typer.echo(f"Fertig: {summary.num_documents} Dokumente, {summary.num_chunks} Textabschnitte gespeichert.")


@app.command()
def ask(question: str) -> None:
    """Beantwortet QUESTION auf Basis der gespeicherten Dokumente."""
    settings = Settings()
    result = answer_question(
        question, settings, llm=create_chat_llm(settings), vectorstore=get_vectorstore(settings)
    )
    typer.echo(result.answer_text)
    typer.echo("\nQuellen:")
    for source in result.sources:
        typer.echo(f"  - {source}")


if __name__ == "__main__":
    app()
