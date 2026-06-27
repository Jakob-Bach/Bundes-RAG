from collections.abc import Callable
from datetime import date
from typing import TYPE_CHECKING, Protocol

from bundesrag.i18n import t
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
    """Renders DipQueryFilters as a human-readable summary for confirmation,
    in the configured output language."""
    lines = [t("planned_query_header", endpoint=filters.endpoint)]
    if filters.datum_start or filters.datum_end:
        lines.append(
            t("filter_zeitraum", start=filters.datum_start or "...", end=filters.datum_end or "...")
        )
    if filters.wahlperiode is not None:
        lines.append(t("filter_wahlperiode", value=filters.wahlperiode))
    if filters.dokumentnummer:
        lines.append(t("filter_dokumentnummer", value=filters.dokumentnummer))
    if filters.zuordnung:
        lines.append(t("filter_zuordnung", value=filters.zuordnung))
    if filters.drucksachetyp:
        lines.append(t("filter_drucksachetyp", value=filters.drucksachetyp))
    if filters.urheber:
        lines.append(t("filter_urheber", value=", ".join(filters.urheber)))
    if filters.ressort_fdf:
        lines.append(t("filter_ressort", value=", ".join(filters.ressort_fdf)))
    if filters.titel:
        lines.append(t("filter_titel", value=", ".join(filters.titel)))
    return "\n".join(lines)


def default_confirm_filters(filters: DipQueryFilters) -> bool:
    print(format_filters(filters))
    return input(t("confirm_use_query_yn")).strip().lower() in (
        "j",
        "ja",
        "y",
        "yes",
    )


class QueryAgent:
    """Turns a German NL prompt into DipQueryFilters, asking the user for
    clarification (via ask_user) when the request is too ambiguous, and for
    confirmation (via confirm_filters) once filters have been proposed."""

    def __init__(
        self,
        structured_llm: StructuredLlm,
        today: date | None = None,
        language: str = "de",
    ) -> None:
        self._llm = structured_llm
        self._today = today or date.today()
        self._language = language

    def build_query(
        self,
        nl_prompt: str,
        ask_user: Callable[[str], str],
        confirm_filters: Callable[[DipQueryFilters], bool] = default_confirm_filters,
    ) -> DipQueryFilters:
        messages = [
            {"role": "system", "content": build_system_prompt(self._today, self._language)},
            {"role": "user", "content": nl_prompt},
        ]
        for _ in range(MAX_CLARIFICATION_ROUNDS):
            result = self._llm.invoke(messages)
            if result.filters is not None:
                if confirm_filters(result.filters):
                    return result.filters
                feedback = ask_user(t("ask_query_feedback"))
                messages.append({"role": "assistant", "content": format_filters(result.filters)})
                messages.append({"role": "user", "content": feedback})
                continue
            question = result.clarification.question
            answer = ask_user(question)
            messages.append({"role": "assistant", "content": question})
            messages.append({"role": "user", "content": answer})
        raise QueryAgentError(t("query_agent_failed"))


def create_query_agent(settings: "Settings") -> QueryAgent:
    from langchain_mistralai import ChatMistralAI

    llm = ChatMistralAI(model=settings.chat_model, api_key=settings.mistral_api_key)
    return QueryAgent(llm.with_structured_output(QueryAgentResult), language=settings.language)
