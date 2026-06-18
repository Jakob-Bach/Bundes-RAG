from datetime import date

import pytest
from pydantic import ValidationError

from bundesrag.query_agent.agent import QueryAgent, QueryAgentError
from bundesrag.query_agent.schema import (
    ClarificationRequest,
    DipQueryFilters,
    QueryAgentResult,
)


def test_filters_reject_content_filters_on_plenarprotokoll():
    with pytest.raises(ValidationError):
        DipQueryFilters(endpoint="plenarprotokoll", urheber=["Bundesregierung"])


def test_filters_allow_content_filters_on_drucksache():
    filters = DipQueryFilters(endpoint="drucksache", urheber=["Bundesregierung"])
    assert filters.urheber == ["Bundesregierung"]


def test_result_requires_exactly_one_branch():
    with pytest.raises(ValidationError):
        QueryAgentResult()
    with pytest.raises(ValidationError):
        QueryAgentResult(
            filters=DipQueryFilters(endpoint="drucksache"),
            clarification=ClarificationRequest(question="?"),
        )


class _StubLlm:
    """Returns queued QueryAgentResults in order, one per .invoke() call."""

    def __init__(self, results):
        self._results = list(results)
        self.calls: list[list[dict]] = []

    def invoke(self, messages):
        self.calls.append(messages)
        return self._results.pop(0)


def test_build_query_returns_filters_directly():
    filters = DipQueryFilters(endpoint="plenarprotokoll", wahlperiode=21)
    llm = _StubLlm([QueryAgentResult(filters=filters)])
    agent = QueryAgent(llm, today=date(2026, 6, 18))

    result = agent.build_query("Plenarprotokolle der 21. Wahlperiode.", ask_user=lambda q: "should not be called")

    assert result == filters
    assert len(llm.calls) == 1


def test_build_query_follows_clarification_loop():
    filters = DipQueryFilters(endpoint="drucksache", wahlperiode=21)
    llm = _StubLlm(
        [
            QueryAgentResult(clarification=ClarificationRequest(question="Welche Wahlperiode meinst du?")),
            QueryAgentResult(filters=filters),
        ]
    )
    asked_questions = []

    def ask_user(question: str) -> str:
        asked_questions.append(question)
        return "21. Wahlperiode"

    agent = QueryAgent(llm, today=date(2026, 6, 18))
    result = agent.build_query("Drucksachen der Bundesregierung.", ask_user=ask_user)

    assert result == filters
    assert asked_questions == ["Welche Wahlperiode meinst du?"]
    assert len(llm.calls) == 2


def test_build_query_raises_after_too_many_clarification_rounds():
    clarification = QueryAgentResult(clarification=ClarificationRequest(question="?"))
    llm = _StubLlm([clarification] * 5)
    agent = QueryAgent(llm, today=date(2026, 6, 18))

    with pytest.raises(QueryAgentError):
        agent.build_query("irgendwas", ask_user=lambda q: "keine Ahnung")
