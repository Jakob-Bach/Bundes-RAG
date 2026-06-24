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


def format_filters(filters: DipQueryFilters) -> str:
    """Renders DipQueryFilters as a human-readable German summary for
    confirmation."""
    lines = [f"Geplante DIP-Abfrage (Endpunkt: {filters.endpoint}):"]
    if filters.datum_start or filters.datum_end:
        lines.append(f"  Zeitraum: {filters.datum_start or '...'} bis {filters.datum_end or '...'}")
    if filters.wahlperiode is not None:
        lines.append(f"  Wahlperiode: {filters.wahlperiode}")
    if filters.dokumentnummer:
        lines.append(f"  Dokumentnummer: {filters.dokumentnummer}")
    if filters.zuordnung:
        lines.append(f"  Zuordnung: {filters.zuordnung}")
    if filters.drucksachetyp:
        lines.append(f"  Drucksachetyp: {filters.drucksachetyp}")
    if filters.urheber:
        lines.append(f"  Urheber: {', '.join(filters.urheber)}")
    if filters.ressort_fdf:
        lines.append(f"  Ressort: {', '.join(filters.ressort_fdf)}")
    if filters.titel:
        lines.append(f"  Titel enthält: {', '.join(filters.titel)}")
    return "\n".join(lines)


def default_confirm_filters(filters: DipQueryFilters) -> bool:
    print(format_filters(filters))
    return input("Abfrage so verwenden? [j/N] ").strip().lower() in (
        "j",
        "ja",
        "y",
        "yes",
    )


class QueryAgent:
    """Turns a German NL prompt into DipQueryFilters, asking the user for
    clarification (via ask_user) when the request is too ambiguous, and for
    confirmation (via confirm_filters) once filters have been proposed."""

    def __init__(self, structured_llm: StructuredLlm, today: date | None = None) -> None:
        self._llm = structured_llm
        self._today = today or date.today()

    def build_query(
        self,
        nl_prompt: str,
        ask_user: Callable[[str], str],
        confirm_filters: Callable[[DipQueryFilters], bool] = default_confirm_filters,
    ) -> DipQueryFilters:
        messages = [
            {"role": "system", "content": build_system_prompt(self._today)},
            {"role": "user", "content": nl_prompt},
        ]
        for _ in range(MAX_CLARIFICATION_ROUNDS):
            result = self._llm.invoke(messages)
            if result.filters is not None:
                if confirm_filters(result.filters):
                    return result.filters
                feedback = ask_user("Was soll an der Abfrage angepasst werden?")
                messages.append({"role": "assistant", "content": format_filters(result.filters)})
                messages.append({"role": "user", "content": feedback})
                continue
            question = result.clarification.question
            answer = ask_user(question)
            messages.append({"role": "assistant", "content": question})
            messages.append({"role": "user", "content": answer})
        raise QueryAgentError(
            "Konnte aus der Anfrage auch nach mehreren Rückfragen keine "
            "gültige DIP-Abfrage erstellen."
        )


def create_query_agent(settings: "Settings") -> QueryAgent:
    from langchain_mistralai import ChatMistralAI

    llm = ChatMistralAI(model=settings.chat_model, api_key=settings.mistral_api_key)
    return QueryAgent(llm.with_structured_output(QueryAgentResult))
