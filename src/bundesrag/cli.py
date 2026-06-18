import typer

from bundesrag.config import Settings
from bundesrag.dip.client import DipClient
from bundesrag.ingestion.pipeline import FetchAborted, run_fetch
from bundesrag.query_agent.agent import create_query_agent
from bundesrag.rag.answer_agent import answer_question, create_chat_llm
from bundesrag.vectorstore import get_vectorstore

app = typer.Typer(help="Lade Bundestagsdokumente herunter und stelle Fragen dazu.")


@app.command()
def fetch(prompt: str) -> None:
    """Lädt Dokumente passend zu PROMPT herunter und indexiert sie."""
    settings = Settings()
    dip_client = DipClient(api_key=settings.dip_api_key)
    try:
        summary = run_fetch(
            prompt,
            settings,
            query_agent=create_query_agent(settings),
            dip_client=dip_client,
            vectorstore=get_vectorstore(settings),
            ask_user=typer.prompt,
            confirm=typer.confirm,
        )
    except FetchAborted as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    finally:
        dip_client.close()
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
