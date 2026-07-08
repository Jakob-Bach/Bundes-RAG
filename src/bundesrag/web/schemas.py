from typing import Literal

from pydantic import BaseModel


class ConfigResponse(BaseModel):
    language: str


class DownloadRequest(BaseModel):
    prompt: str


class DownloadSummaryResponse(BaseModel):
    num_documents: int
    num_failed: int
    num_skipped: int


class IndexSummaryResponse(BaseModel):
    num_documents: int
    num_chunks: int


class IndexCountsResponse(BaseModel):
    """Counts shown when an index job starts: pending vs. already indexed."""

    num_to_index: int
    num_indexed: int


class DeleteSummaryResponse(BaseModel):
    num_files: int


class ClearRequest(BaseModel):
    confirmed: bool


class FileStatusResponse(BaseModel):
    pdf_path: str
    indexed: bool


class StatusResponse(BaseModel):
    num_downloaded: int
    num_indexed: int
    files: list[FileStatusResponse]


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer_text: str
    sources: list[str]


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
