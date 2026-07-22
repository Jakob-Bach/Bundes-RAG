"""Token-usage tracking for the Mistral API calls (chat + embeddings).

Every pipeline that talks to Mistral creates a `UsageTracker` and records what
the operation consumed: chat calls report their `usage_metadata` (the LangChain
standard field on chat responses), embeddings are captured via httpx event
hooks on the `MistralAIEmbeddings` client — LangChain discards the `usage`
field of the embeddings API response, but the raw httpx response still carries
it. Only the sync client is hooked; the pipelines never use the async one.

Finished operations are accumulated per operation kind ("download", "index",
"ask") in `data/usage_stats.json` (`record_operation`), which the status
pipeline reads back (`load_usage_totals`) to show all-time totals.
"""

import json
import logging
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import httpx
from pydantic import BaseModel

from bundesrag.config import Settings

logger = logging.getLogger(__name__)

# Operation kinds under which usage is accumulated in the stats file.
OPERATION_KINDS = ("download", "index", "ask")


class OperationUsage(BaseModel):
    """What one operation consumed on the Mistral API."""

    chat_input_tokens: int = 0
    chat_output_tokens: int = 0
    chat_calls: int = 0
    embedding_tokens: int = 0
    embedding_calls: int = 0
    # Wall time spent waiting on the Mistral API (chat + embeddings requests).
    llm_seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.chat_input_tokens + self.chat_output_tokens + self.embedding_tokens

    @property
    def has_usage(self) -> bool:
        return self.chat_calls > 0 or self.embedding_calls > 0

    def add(self, other: "OperationUsage") -> None:
        self.chat_input_tokens += other.chat_input_tokens
        self.chat_output_tokens += other.chat_output_tokens
        self.chat_calls += other.chat_calls
        self.embedding_tokens += other.embedding_tokens
        self.embedding_calls += other.embedding_calls
        self.llm_seconds += other.llm_seconds


class UsageTotals(OperationUsage):
    """All-time accumulated usage of one operation kind."""

    num_operations: int = 0


def estimate_cost(usage: OperationUsage, settings: Settings) -> float | None:
    """Estimated cost of `usage` from the per-million-token prices in Settings.

    Returns None when a price needed for the consumed token kinds is unset —
    the caller then simply omits the cost statistic.
    """
    cost = 0.0
    if usage.chat_input_tokens or usage.chat_output_tokens:
        if (
            settings.chat_input_price_per_mtok is None
            or settings.chat_output_price_per_mtok is None
        ):
            return None
        cost += usage.chat_input_tokens / 1_000_000 * settings.chat_input_price_per_mtok
        cost += usage.chat_output_tokens / 1_000_000 * settings.chat_output_price_per_mtok
    if usage.embedding_tokens:
        if settings.embedding_price_per_mtok is None:
            return None
        cost += usage.embedding_tokens / 1_000_000 * settings.embedding_price_per_mtok
    return cost


class UsageTracker:
    """Collects the Mistral usage of one operation into an OperationUsage."""

    def __init__(self) -> None:
        self.usage = OperationUsage()

    def record_chat(self, response: object, seconds: float) -> None:
        """Record one chat LLM call from its response object.

        `response` is the raw chat response (AIMessage) when available; test
        fakes without `usage_metadata` still count as a call, just with
        unknown token numbers.
        """
        self.usage.chat_calls += 1
        self.usage.llm_seconds += seconds
        # The Mapping check also keeps test fakes (e.g. Mock responses, whose
        # attribute access never fails) from producing nonsense token counts.
        metadata = getattr(response, "usage_metadata", None)
        if isinstance(metadata, Mapping):
            self.usage.chat_input_tokens += metadata.get("input_tokens") or 0
            self.usage.chat_output_tokens += metadata.get("output_tokens") or 0

    @contextmanager
    def track_embeddings(self, vectorstore: object) -> Iterator[None]:
        """Capture embeddings usage while the block runs.

        Attaches httpx event hooks to the vector store's Mistral embeddings
        client that read the `usage` field of each embeddings API response
        (which LangChain itself throws away). A no-op for vector stores
        without such a client (fakes, `with_embeddings=False`).
        """
        embeddings = getattr(vectorstore, "embeddings", None)
        client = getattr(embeddings, "client", None)
        if not isinstance(client, httpx.Client):
            yield
            return

        def on_request(request: httpx.Request) -> None:
            request.extensions["bundesrag_start"] = time.perf_counter()

        def on_response(response: httpx.Response) -> None:
            start = response.request.extensions.get("bundesrag_start")
            if start is not None:
                self.usage.llm_seconds += time.perf_counter() - start
            if not response.is_success:
                return
            try:
                response.read()
                usage = response.json().get("usage") or {}
                tokens = usage.get("total_tokens")
            except Exception:
                logger.warning("could not read embeddings usage from response", exc_info=True)
                return
            if tokens is not None:
                self.usage.embedding_calls += 1
                self.usage.embedding_tokens += tokens

        client.event_hooks["request"].append(on_request)
        client.event_hooks["response"].append(on_response)
        try:
            yield
        finally:
            client.event_hooks["request"].remove(on_request)
            client.event_hooks["response"].remove(on_response)


def usage_stats_path(settings: Settings) -> Path:
    return settings.data_dir / "usage_stats.json"


# Guards the read-modify-write of the stats file against concurrent web jobs.
_STATS_LOCK = threading.Lock()


def load_usage_totals(settings: Settings) -> dict[str, UsageTotals]:
    path = usage_stats_path(settings)
    if not path.exists():
        return {}
    # Statistics only — an unreadable/corrupt file degrades to empty totals
    # (with a log warning) instead of failing status runs.
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {key: UsageTotals.model_validate(value) for key, value in raw.items()}
    except Exception:
        logger.warning("could not read usage stats %s, starting empty", path, exc_info=True)
        return {}


def _save_usage_totals(settings: Settings, totals: dict[str, UsageTotals]) -> None:
    path = usage_stats_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {key: value.model_dump(mode="json") for key, value in totals.items()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def record_operation(settings: Settings, operation: str, usage: OperationUsage) -> None:
    """Log an operation's usage and add it to the all-time totals.

    Called by the pipelines in a `finally`, so aborted/failed runs still
    account for the tokens they consumed. Operations that never reached the
    Mistral API (e.g. nothing to index) are skipped entirely.
    """
    if not usage.has_usage:
        return
    logger.info(
        "mistral usage (%s): %d input + %d output chat tokens in %d call(s), "
        "%d embedding tokens in %d call(s), %.1fs API time",
        operation,
        usage.chat_input_tokens,
        usage.chat_output_tokens,
        usage.chat_calls,
        usage.embedding_tokens,
        usage.embedding_calls,
        usage.llm_seconds,
    )
    with _STATS_LOCK:
        totals = load_usage_totals(settings)
        entry = totals.setdefault(operation, UsageTotals())
        entry.add(usage)
        entry.num_operations += 1
        _save_usage_totals(settings, totals)
