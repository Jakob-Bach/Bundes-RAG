from collections.abc import Callable
from datetime import date
from typing import TYPE_CHECKING, Protocol

from bundesrag.query_agent.prompts import build_system_prompt
from bundesrag.query_agent.schema import DipQueryFilters, QueryAgentResult

if TYPE_CHECKING:
    from bundesrag.config import Settings

MAX_CLARIFICATION_ROUNDS = 5


class QueryAgentError(RuntimeError):
    pass


class StructuredLlm(Protocol):
    def invoke(self, messages: list[dict]) -> QueryAgentResult: ...


class QueryAgent:
    """Turns a German NL prompt into DipQueryFilters, asking the user for
    clarification (via ask_user) when the request is too ambiguous."""

    def __init__(self, structured_llm: StructuredLlm, today: date | None = None) -> None:
        self._llm = structured_llm
        self._today = today or date.today()

    def build_query(self, nl_prompt: str, ask_user: Callable[[str], str]) -> DipQueryFilters:
        messages = [
            {"role": "system", "content": build_system_prompt(self._today)},
            {"role": "user", "content": nl_prompt},
        ]
        for _ in range(MAX_CLARIFICATION_ROUNDS):
            result = self._llm.invoke(messages)
            if result.filters is not None:
                return result.filters
            question = result.clarification.question
            answer = ask_user(question)
            messages.append({"role": "assistant", "content": question})
            messages.append({"role": "user", "content": answer})
        raise QueryAgentError(
            "Konnte aus der Anfrage auch nach mehreren Rückfragen keine gültige DIP-Abfrage erstellen."
        )


def create_query_agent(settings: "Settings") -> QueryAgent:
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model=settings.chat_model, api_key=settings.anthropic_api_key)
    return QueryAgent(llm.with_structured_output(QueryAgentResult))
