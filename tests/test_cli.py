from typer.testing import CliRunner

from bundesrag import cli
from bundesrag.ingestion.pipeline import (
    DeleteSummary,
    DownloadAborted,
    DownloadSummary,
    IndexSummary,
)
from bundesrag.rag.answer_agent import AnswerResult

runner = CliRunner()


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


def test_index_command_reports_summary(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    mocker.patch.object(cli, "run_index", return_value=IndexSummary(num_documents=3, num_chunks=12))

    result = runner.invoke(cli.app, ["index"])

    assert result.exit_code == 0
    assert "3 Dokumente" in result.stdout
    assert "12 Textabschnitte" in result.stdout


def test_clear_command_reports_summary_when_confirmed(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    mocker.patch.object(cli, "run_delete_all", return_value=DeleteSummary(num_files=5))

    result = runner.invoke(cli.app, ["clear"], input="y\n")

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


def test_ask_command_prints_answer_and_sources(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    mocker.patch.object(cli, "create_chat_llm", return_value=mocker.Mock())
    mocker.patch.object(
        cli,
        "answer_question",
        return_value=AnswerResult(answer_text="Die Antwort.", sources=["Antrag 19/1, S. 1"]),
    )

    result = runner.invoke(cli.app, ["ask", "Worum geht es?"])

    assert result.exit_code == 0
    assert "Die Antwort." in result.stdout
    assert "Antrag 19/1, S. 1" in result.stdout
