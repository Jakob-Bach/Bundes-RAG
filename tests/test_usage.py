import json
from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from bundesrag.query_agent.agent import QueryAgent
from bundesrag.query_agent.schema import DipQueryFilters, QueryAgentResult
from bundesrag.usage import (
    OperationUsage,
    UsageTracker,
    estimate_cost,
    load_usage_totals,
    record_operation,
    usage_stats_path,
)


def test_operation_usage_totals_and_add():
    usage = OperationUsage(chat_input_tokens=100, chat_output_tokens=20, embedding_tokens=300)
    other = OperationUsage(chat_input_tokens=1, chat_calls=1, llm_seconds=2.5)

    usage.add(other)

    assert usage.chat_input_tokens == 101
    assert usage.total_tokens == 101 + 20 + 300
    assert usage.llm_seconds == 2.5


def test_estimate_cost_uses_prices_per_million_tokens(settings):
    settings.chat_input_price_per_mtok = 2.0
    settings.chat_output_price_per_mtok = 6.0
    settings.embedding_price_per_mtok = 0.1
    usage = OperationUsage(
        chat_input_tokens=1_000_000, chat_output_tokens=500_000, embedding_tokens=2_000_000
    )

    cost = estimate_cost(usage, settings)

    assert cost == 2.0 + 3.0 + 0.2


def test_estimate_cost_is_none_when_needed_price_unset(settings):
    settings.chat_input_price_per_mtok = 2.0
    settings.embedding_price_per_mtok = None
    assert estimate_cost(OperationUsage(embedding_tokens=100), settings) is None
    # Chat-only usage doesn't need the embedding price.
    assert estimate_cost(OperationUsage(chat_input_tokens=100), settings) == pytest.approx(0.0002)


def test_record_chat_reads_usage_metadata():
    tracker = UsageTracker()
    response = SimpleNamespace(usage_metadata={"input_tokens": 10, "output_tokens": 3})

    tracker.record_chat(response, seconds=1.5)
    tracker.record_chat("plain string without metadata", seconds=0.5)

    assert tracker.usage.chat_calls == 2
    assert tracker.usage.chat_input_tokens == 10
    assert tracker.usage.chat_output_tokens == 3
    assert tracker.usage.llm_seconds == 2.0


def _embeddings_vectorstore(handler) -> SimpleNamespace:
    """A fake vector store whose embeddings client is a real httpx.Client,
    so track_embeddings attaches its event hooks like in production."""
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.test")
    return SimpleNamespace(embeddings=SimpleNamespace(client=client))


def test_track_embeddings_reads_usage_from_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": [], "usage": {"prompt_tokens": 42, "total_tokens": 42}}
        )

    vectorstore = _embeddings_vectorstore(handler)
    tracker = UsageTracker()
    with tracker.track_embeddings(vectorstore):
        vectorstore.embeddings.client.post("/embeddings", json={})
        vectorstore.embeddings.client.post("/embeddings", json={})

    assert tracker.usage.embedding_calls == 2
    assert tracker.usage.embedding_tokens == 84
    assert tracker.usage.llm_seconds > 0
    # Hooks are removed after the block: further calls aren't counted.
    vectorstore.embeddings.client.post("/embeddings", json={})
    assert tracker.usage.embedding_calls == 2


def test_track_embeddings_ignores_error_responses():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "rate limited"})

    vectorstore = _embeddings_vectorstore(handler)
    tracker = UsageTracker()
    with tracker.track_embeddings(vectorstore):
        vectorstore.embeddings.client.post("/embeddings", json={})

    assert tracker.usage.embedding_calls == 0
    assert tracker.usage.embedding_tokens == 0
    # The wall time still counts — the failed request was still waited on.
    assert tracker.usage.llm_seconds > 0


def test_track_embeddings_is_a_noop_without_httpx_client(mocker):
    tracker = UsageTracker()
    with tracker.track_embeddings(mocker.Mock()):
        pass
    assert not tracker.usage.has_usage


def test_record_operation_accumulates_totals(settings):
    record_operation(settings, "ask", OperationUsage(chat_input_tokens=10, chat_calls=1))
    record_operation(settings, "ask", OperationUsage(chat_input_tokens=5, chat_calls=1))
    record_operation(settings, "index", OperationUsage(embedding_tokens=100, embedding_calls=2))

    totals = load_usage_totals(settings)

    assert totals["ask"].num_operations == 2
    assert totals["ask"].chat_input_tokens == 15
    assert totals["index"].num_operations == 1
    assert totals["index"].embedding_tokens == 100


def test_record_operation_skips_operations_without_api_calls(settings):
    record_operation(settings, "index", OperationUsage())

    assert not usage_stats_path(settings).exists()


def test_load_usage_totals_tolerates_corrupt_file(settings):
    path = usage_stats_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")

    assert load_usage_totals(settings) == {}
    # Recording on top of the corrupt file starts fresh instead of failing.
    record_operation(settings, "ask", OperationUsage(chat_calls=1))
    assert load_usage_totals(settings)["ask"].num_operations == 1
    assert json.loads(path.read_text(encoding="utf-8"))["ask"]["chat_calls"] == 1


class _RawStubLlm:
    """Returns include_raw-style dicts like the production structured LLM."""

    def __init__(self, results):
        self._results = list(results)

    def invoke(self, messages):
        parsed = self._results.pop(0)
        raw = SimpleNamespace(usage_metadata={"input_tokens": 7, "output_tokens": 2})
        return {"raw": raw, "parsed": parsed, "parsing_error": None}


def test_query_agent_records_usage_from_raw_results():
    filters = DipQueryFilters(endpoint="plenarprotokoll", wahlperiode=21)
    llm = _RawStubLlm([QueryAgentResult(filters=filters)])
    agent = QueryAgent(llm, today=date(2026, 6, 18))
    tracker = UsageTracker()

    result = agent.build_query(
        "Plenarprotokolle der 21. Wahlperiode.",
        ask_user=lambda q: "",
        confirm_filters=lambda f: True,
        usage=tracker,
    )

    assert result == filters
    assert tracker.usage.chat_calls == 1
    assert tracker.usage.chat_input_tokens == 7
    assert tracker.usage.chat_output_tokens == 2
