from typer.testing import CliRunner

from bundesrag import cli
from bundesrag.ingestion.pipeline import FetchAborted, FetchSummary
from bundesrag.rag.answer_agent import AnswerResult

runner = CliRunner()


def test_fetch_command_reports_summary(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "DipClient", return_value=mocker.Mock())
    mocker.patch.object(cli, "create_query_agent", return_value=mocker.Mock())
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    mocker.patch.object(cli, "run_fetch", return_value=FetchSummary(num_documents=3, num_chunks=12))

    result = runner.invoke(cli.app, ["fetch", "Plenarprotokolle der 21. Wahlperiode."])

    assert result.exit_code == 0
    assert "3 Dokumente" in result.stdout
    assert "12 Textabschnitte" in result.stdout


def test_fetch_command_reports_abort_with_nonzero_exit(settings, mocker):
    mocker.patch.object(cli, "Settings", return_value=settings)
    mocker.patch.object(cli, "DipClient", return_value=mocker.Mock())
    mocker.patch.object(cli, "create_query_agent", return_value=mocker.Mock())
    mocker.patch.object(cli, "get_vectorstore", return_value=mocker.Mock())
    mocker.patch.object(cli, "run_fetch", side_effect=FetchAborted("zu viele Dokumente"))

    result = runner.invoke(cli.app, ["fetch", "Drucksachen der 21. Wahlperiode."])

    assert result.exit_code == 1
    assert "zu viele Dokumente" in result.stdout


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
