import logging

import typer

from bundesrag.config import Settings, detect_language
from bundesrag.dip.client import DipClient
from bundesrag.i18n import set_language, t, yes_no_tokens
from bundesrag.ingestion.pipeline import (
    DownloadAborted,
    DownloadCounts,
    IndexCounts,
    run_delete_all,
    run_download,
    run_index,
    run_status,
)
from bundesrag.logging_config import LOGGER_NAME, setup_logging
from bundesrag.query_agent.agent import create_query_agent, format_filters
from bundesrag.query_agent.schema import DipQueryFilters
from bundesrag.rag.answer_agent import answer_question, create_chat_llm
from bundesrag.usage import OPERATION_KINDS, OperationUsage, estimate_cost
from bundesrag.vectorstore import get_vectorstore

# Help text is rendered from the locale files at import time (the command
# decorators below run before any command's _init()), so the language must be
# known here already; detect_language() reads it without requiring API keys.
set_language(detect_language())

app = typer.Typer(help=t("app_help"))

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


def _echo_index_counts(counts: IndexCounts) -> None:
    typer.echo(t("index_counts", num_to_index=counts.num_to_index, num_indexed=counts.num_indexed))


def _echo_usage(usage: OperationUsage, settings: Settings) -> None:
    """Prints an operation's Mistral usage; silent when no API call was made."""
    if not usage.has_usage:
        return
    typer.echo(t("usage_header"))
    if usage.chat_calls:
        typer.echo(
            t(
                "usage_chat",
                input_tokens=usage.chat_input_tokens,
                output_tokens=usage.chat_output_tokens,
                num_calls=usage.chat_calls,
            )
        )
    if usage.embedding_calls:
        typer.echo(
            t("usage_embedding", tokens=usage.embedding_tokens, num_calls=usage.embedding_calls)
        )
    typer.echo(t("usage_time", seconds=f"{usage.llm_seconds:.1f}"))
    cost = estimate_cost(usage, settings)
    if cost is not None:
        typer.echo(t("usage_cost", cost=f"{cost:.4f}", currency=settings.price_currency))


def _confirm_count(counts: DownloadCounts) -> int:
    raw = typer.prompt(
        t(
            "ask_download_count",
            num_matched=counts.num_matched,
            num_existing=counts.num_existing,
            num_to_download=counts.num_to_download,
        ),
        default=str(counts.num_to_download),
    )
    try:
        chosen = int(raw)
    except ValueError:
        return counts.num_to_download
    return max(0, min(chosen, counts.num_to_download))


@app.command(help=t("download_help"))
def download(prompt: str) -> None:
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
        "download succeeded: %d documents, %d failed, %d already downloaded",
        summary.num_documents,
        summary.num_failed,
        summary.num_skipped,
    )
    typer.echo(t("download_done", num_documents=summary.num_documents))
    if summary.num_skipped:
        typer.echo(t("download_skipped_existing", num_skipped=summary.num_skipped))
    if summary.num_failed:
        typer.echo(t("download_partial_failure", num_failed=summary.num_failed))
    _echo_usage(summary.usage, settings)


@app.command(help=t("index_help"))
def index() -> None:
    settings = _init()
    logger.info("index command invoked")
    try:
        summary = run_index(
            settings, vectorstore=get_vectorstore(settings), on_counts=_echo_index_counts
        )
    except Exception:
        logger.exception("index failed")
        typer.echo(t("unexpected_error"))
        raise typer.Exit(code=1) from None
    logger.info(
        "index succeeded: %d documents, %d chunks", summary.num_documents, summary.num_chunks
    )
    typer.echo(t("index_done", num_documents=summary.num_documents, num_chunks=summary.num_chunks))
    _echo_usage(summary.usage, settings)


@app.command(help=t("clear_help"))
def clear(
    yes: bool = typer.Option(False, "--yes", "-y", help=t("clear_yes_option_help")),
) -> None:
    settings = _init()
    logger.info("clear command invoked")
    if not yes and not _confirm(t("confirm_delete_all_yn")):
        logger.warning("clear aborted: user declined confirmation")
        raise typer.Exit(code=1)
    try:
        summary = run_delete_all(
            settings, vectorstore=get_vectorstore(settings, with_embeddings=False)
        )
    except Exception:
        logger.exception("clear failed")
        typer.echo(t("unexpected_error"))
        raise typer.Exit(code=1) from None
    logger.info("clear succeeded: %d files deleted", summary.num_files)
    typer.echo(t("delete_done", num_files=summary.num_files))


def _format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            break
        value /= 1024
    return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"


@app.command(help=t("status_help"))
def status() -> None:
    settings = _init()
    logger.info("status command invoked")
    try:
        summary = run_status(settings, vectorstore=get_vectorstore(settings, with_embeddings=False))
    except Exception:
        logger.exception("status failed")
        typer.echo(t("unexpected_error"))
        raise typer.Exit(code=1) from None
    logger.info(
        "status succeeded: %d downloaded, %d indexed, %d chunks",
        summary.num_downloaded,
        summary.num_indexed,
        summary.num_chunks,
    )
    typer.echo(t("status_num_downloaded", count=summary.num_downloaded))
    typer.echo(t("status_num_indexed", count=summary.num_indexed))
    typer.echo(t("status_num_chunks", count=summary.num_chunks))
    if summary.num_chunks != summary.num_manifest_chunks:
        typer.echo(
            t(
                "status_chunk_mismatch",
                num_chunks=summary.num_chunks,
                num_expected=summary.num_manifest_chunks,
            )
        )
    typer.echo(t("status_pdf_size", size=_format_size(summary.pdf_size_bytes)))
    typer.echo(t("status_vectorstore_size", size=_format_size(summary.vectorstore_size_bytes)))
    if summary.usage_totals:
        typer.echo(t("usage_totals_header"))
        for operation in OPERATION_KINDS:
            totals = summary.usage_totals.get(operation)
            if totals is None or not totals.has_usage:
                continue
            line = t(
                "usage_totals_line",
                operation=t(f"usage_op_{operation}"),
                tokens=totals.total_tokens,
                num_operations=totals.num_operations,
                seconds=f"{totals.llm_seconds:.1f}",
            )
            cost = estimate_cost(totals, settings)
            if cost is not None:
                line += t("usage_cost_suffix", cost=f"{cost:.4f}", currency=settings.price_currency)
            typer.echo(line)
    typer.echo(t("status_files_header"))
    for file in summary.files:
        status_label = t("status_file_indexed") if file.indexed else t("status_file_not_indexed")
        typer.echo(f"  - {file.pdf_path} ({status_label})")


@app.command(help=t("serve_help"))
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help=t("serve_host_option_help")),
    port: int = typer.Option(8000, "--port", help=t("serve_port_option_help")),
    reload: bool = typer.Option(False, "--reload", help=t("serve_reload_option_help")),
) -> None:
    import uvicorn

    _init()
    logger.info("starting web server on %s:%d", host, port)
    typer.echo(t("serve_started", host=host, port=port))
    uvicorn.run("bundesrag.web.app:create_app", host=host, port=port, reload=reload, factory=True)


@app.command(help=t("ask_help"))
def ask(question: str) -> None:
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
        typer.echo(f"  [{source.index}] {source.citation}")
    _echo_usage(result.usage, settings)


if __name__ == "__main__":
    app()
