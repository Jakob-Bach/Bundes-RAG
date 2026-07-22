from typing import Literal

from pydantic import BaseModel

from bundesrag.config import Settings
from bundesrag.usage import OperationUsage, UsageTotals, estimate_cost


class ConfigResponse(BaseModel):
    language: str


class DownloadRequest(BaseModel):
    prompt: str


class UsageResponse(BaseModel):
    """Mistral usage of one operation, plus the server-side cost estimate.

    `cost` is None when a needed price setting is unset; the SPA then omits
    the cost line.
    """

    chat_input_tokens: int
    chat_output_tokens: int
    chat_calls: int
    embedding_tokens: int
    embedding_calls: int
    llm_seconds: float
    total_tokens: int
    cost: float | None = None
    currency: str


class UsageTotalsResponse(UsageResponse):
    """All-time accumulated usage of one operation kind (status view)."""

    num_operations: int


def usage_response(usage: OperationUsage, settings: Settings) -> UsageResponse | None:
    """Build the response for an operation's usage; None when nothing was used
    (the SPA then shows no usage block at all)."""
    if not usage.has_usage:
        return None
    return UsageResponse(
        **usage.model_dump(),
        total_tokens=usage.total_tokens,
        cost=estimate_cost(usage, settings),
        currency=settings.price_currency,
    )


def usage_totals_response(
    totals: dict[str, UsageTotals], settings: Settings
) -> dict[str, UsageTotalsResponse]:
    return {
        operation: UsageTotalsResponse(
            **entry.model_dump(),
            total_tokens=entry.total_tokens,
            cost=estimate_cost(entry, settings),
            currency=settings.price_currency,
        )
        for operation, entry in totals.items()
        if entry.has_usage
    }


class DownloadSummaryResponse(BaseModel):
    num_documents: int
    num_failed: int
    num_skipped: int
    usage: UsageResponse | None = None


class IndexSummaryResponse(BaseModel):
    num_documents: int
    num_chunks: int
    usage: UsageResponse | None = None


class IndexCountsResponse(BaseModel):
    """Counts shown when an index job starts: pending vs. already indexed."""

    num_to_index: int
    num_indexed: int


class DeleteSummaryResponse(BaseModel):
    num_files: int


class ClearRequest(BaseModel):
    confirmed: bool


class DeleteFileRequest(BaseModel):
    # The pdf_path exactly as returned by GET /api/status; paths that the
    # status scan doesn't report are rejected with 404.
    pdf_path: str
    confirmed: bool


class DocumentInfoResponse(BaseModel):
    """Per-document metadata: from the vector store's chunk metadata for
    indexed documents, from the pending manifest (page count read from the
    PDF, no chunk count yet) for not-yet-indexed ones."""

    doc_id: str | None = None
    dokumentnummer: str | None = None
    citation_label: str | None = None
    datum: str | None = None
    source_url: str | None = None
    num_chunks: int | None = None
    num_pages: int | None = None


class FileStatusResponse(BaseModel):
    pdf_path: str
    indexed: bool
    kind: str = ""
    info: DocumentInfoResponse | None = None


class StatusResponse(BaseModel):
    num_downloaded: int
    num_indexed: int
    num_chunks: int
    # Chunk total recorded in the indexed-docs manifest; the SPA warns when it
    # differs from num_chunks (the vector store's actual count).
    num_manifest_chunks: int
    pdf_size_bytes: int
    vectorstore_size_bytes: int
    files: list[FileStatusResponse]
    # All-time Mistral usage per operation kind ("download"/"index"/"ask").
    usage_totals: dict[str, UsageTotalsResponse] = {}


class AskRequest(BaseModel):
    question: str


class SourceResponse(BaseModel):
    """One retrieved chunk; `index` matches the [n] citations in answer_text.

    The SPA renders each [n] as a link to the source with that index, links
    the citation to `source_url#page={page}`, and shows `text` (the retrieved
    chunk) in an expandable panel.
    """

    index: int
    citation: str
    text: str
    page: int | None = None
    source_url: str | None = None


class AskResponse(BaseModel):
    answer_text: str
    sources: list[SourceResponse]
    usage: UsageResponse | None = None


class PendingInputResponse(BaseModel):
    """Describes what input a waiting_input job needs from the user next."""

    kind: Literal["ask_user", "confirm_filters", "confirm_count"]
    question: str | None = None
    filters_text: str | None = None
    num_matched: int | None = None
    num_existing: int | None = None
    num_to_download: int | None = None


class JobProgressResponse(BaseModel):
    """Per-item progress of a running job's long loop (downloads/indexing)."""

    current: int
    total: int


class JobResponse(BaseModel):
    id: str
    status: Literal["running", "waiting_input", "done", "error", "cancelled"]
    pending: PendingInputResponse | None = None
    progress: JobProgressResponse | None = None
    counts: IndexCountsResponse | None = None
    result: DownloadSummaryResponse | IndexSummaryResponse | None = None
    error: str | None = None


class RespondRequest(BaseModel):
    # A single string field for all pending-input kinds: confirm_filters answers
    # are "true"/"false", confirm_count answers are stringified integers.
    answer: str
