from importlib import import_module

from typer.testing import CliRunner

from bundesrag import cli
from bundesrag.config import detect_language
from bundesrag.ingestion.pipeline import (
    DeleteSummary,
    DownloadAborted,
    DownloadSummary,
    FileStatus,
    IndexCounts,
    IndexSummary,
    StatusSummary,
)
from bundesrag.rag.answer_agent import AnswerResult, Source

runner = CliRunner()


def test_help_texts_come_from_locale_files():
    # Help strings are resolved when bundesrag.cli is imported, in the
    # language detect_language() reports for this environment.
    messages = import_module(f"bundesrag.locales.{detect_language()}").MESSAGES
    assert cli.app.info.help == messages["app_help"]
    helps = {info.name or info.callback.__name__: info.help for info in cli.app.registered_commands}
    for command in ("download", "index", "ask", "status", "clear", "serve"):
        assert helps[command] == messages[f"{command}_help"]


def test_download_command_reports_summary(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "DipClient", return_value=mocker.Mock())
    mocker.patch.object(cli, "create_query_agent", return_value=mocker.Mock())
    mocker.patch.object(cli, "run_download", return_value=DownloadSummary(num_documents=3))

    result = runner.invoke(cli.app, ["download", "Plenarprotokolle der 21. Wahlperiode."])

    assert result.exit_code == 0
    assert "3 Dokumente" in result.stdout


def test_download_command_reports_abort_with_nonzero_exit(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "DipClient", return_value=mocker.Mock())
    mocker.patch.object(cli, "create_query_agent", return_value=mocker.Mock())
    mocker.patch.object(cli, "run_download", side_effect=DownloadAborted("zu viele Dokumente"))

    result = runner.invoke(cli.app, ["download", "Drucksachen der 21. Wahlperiode."])

    assert result.exit_code == 1
    assert "zu viele Dokumente" in result.stdout


def test_index_command_reports_counts_and_summary(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())

    def fake_run_index(settings, *, vectorstore, on_counts=None, **kwargs):
        on_counts(IndexCounts(num_to_index=3, num_indexed=5))
        return IndexSummary(num_documents=3, num_chunks=12)

    mocker.patch.object(cli, "run_index", side_effect=fake_run_index)

    result = runner.invoke(cli.app, ["index"])

    assert result.exit_code == 0
    assert "3 Dokument(e) zu indexieren, 5 bereits indexiert" in result.stdout
    assert "3 Dokumente" in result.stdout
    assert "12 Textabschnitte" in result.stdout


def test_clear_command_reports_summary_when_confirmed(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    mocker.patch.object(cli, "run_delete_all", return_value=DeleteSummary(num_files=5))

    result = runner.invoke(cli.app, ["clear"], input="j\n")

    assert result.exit_code == 0
    assert "5 Dateien" in result.stdout


def test_clear_command_skips_confirmation_with_yes_flag(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    run_delete_all = mocker.patch.object(
        cli, "run_delete_all", return_value=DeleteSummary(num_files=2)
    )

    result = runner.invoke(cli.app, ["clear", "--yes"])

    assert result.exit_code == 0
    run_delete_all.assert_called_once()


def test_clear_command_aborts_when_user_declines_confirmation(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    run_delete_all = mocker.patch.object(cli, "run_delete_all")

    result = runner.invoke(cli.app, ["clear"], input="n\n")

    assert result.exit_code == 1
    run_delete_all.assert_not_called()


def test_status_command_reports_counts_and_file_statuses(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    mocker.patch.object(
        cli,
        "run_status",
        return_value=StatusSummary(
            num_downloaded=2,
            num_indexed=1,
            files=[
                FileStatus(pdf_path=settings.pdf_dir / "drucksache" / "19_1.pdf", indexed=True),
                FileStatus(pdf_path=settings.pdf_dir / "drucksache" / "19_2.pdf", indexed=False),
            ],
            num_chunks=12,
            num_manifest_chunks=12,
            pdf_size_bytes=2048,
            vectorstore_size_bytes=512,
        ),
    )

    result = runner.invoke(cli.app, ["status"])

    assert result.exit_code == 0
    assert "Heruntergeladen: 2" in result.stdout
    assert "Indexiert: 1" in result.stdout
    assert "Textabschnitte in der Vektordatenbank: 12" in result.stdout
    assert "Warnung" not in result.stdout
    assert "Speicherplatz PDFs: 2.0 KB" in result.stdout
    assert "Speicherplatz Vektordatenbank: 512 B" in result.stdout
    assert "19_1.pdf" in result.stdout
    assert "19_2.pdf" in result.stdout


def test_status_command_warns_on_chunk_count_mismatch(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    mocker.patch.object(
        cli,
        "run_status",
        return_value=StatusSummary(
            num_downloaded=1,
            num_indexed=1,
            files=[],
            num_chunks=12,
            num_manifest_chunks=10,
        ),
    )

    result = runner.invoke(cli.app, ["status"])

    assert result.exit_code == 0
    assert "Warnung" in result.stdout
    assert "12" in result.stdout
    assert "10" in result.stdout


def test_ask_command_prints_answer_and_sources(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    mocker.patch.object(cli, "create_chat_llm", return_value=mocker.Mock())
    mocker.patch.object(
        cli,
        "answer_question",
        return_value=AnswerResult(
            answer_text="Die Antwort.",
            sources=[
                Source(
                    index=1,
                    citation="Antrag 19/1, S. 1",
                    text="Auszug",
                    page=1,
                    source_url=None,
                )
            ],
        ),
    )

    result = runner.invoke(cli.app, ["ask", "Worum geht es?"])

    assert result.exit_code == 0
    assert "Die Antwort." in result.stdout
    assert "[1] Antrag 19/1, S. 1" in result.stdout
