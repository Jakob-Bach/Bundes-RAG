import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from bundesrag.i18n import t
from bundesrag.ingestion.pipeline import OperationCancelled
from bundesrag.web.schemas import (
    IndexCountsResponse,
    JobProgressResponse,
    PendingInputResponse,
)


class JobNotFoundError(KeyError):
    pass


class JobNotWaitingError(RuntimeError):
    pass


class JobNotCancellableError(RuntimeError):
    pass


@dataclass
class Job:
    id: str
    status: Literal["running", "waiting_input", "done", "error", "cancelled"] = "running"
    pending: PendingInputResponse | None = None
    progress: JobProgressResponse | None = None
    counts: IndexCountsResponse | None = None
    result: object | None = None
    error: str | None = None
    _answer_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _answer_value: str | None = field(default=None, repr=False)
    _cancel_requested: bool = field(default=False, repr=False)


class JobManager:
    """In-process store for background jobs, bridging the pipelines' blocking
    ask_user/confirm_* callables to HTTP round trips: the worker thread blocks
    in wait_for_answer() until a request delivers the answer via
    provide_answer(). Requires a single server process (no multiple workers)."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self) -> Job:
        job = Job(id=str(uuid.uuid4()))
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def wait_for_answer(self, job: Job, pending: PendingInputResponse) -> str:
        # A fresh Event per round avoids any stale set() from a previous round.
        event = threading.Event()
        with self._lock:
            # A cancel that arrived while the worker was busy would have set
            # the previous event, not this fresh one — honor it before waiting.
            if job._cancel_requested:
                raise OperationCancelled(t("operation_cancelled"))
            job._answer_event = event
            job._answer_value = None
            job.pending = pending
            job.status = "waiting_input"
        event.wait()
        with self._lock:
            if job._cancel_requested:
                job.pending = None
                raise OperationCancelled(t("operation_cancelled"))
            answer = job._answer_value
            job.status = "running"
            job.pending = None
        return answer if answer is not None else ""

    def set_progress(self, job: Job, current: int, total: int) -> None:
        with self._lock:
            job.progress = JobProgressResponse(current=current, total=total)

    def set_counts(self, job: Job, counts: IndexCountsResponse) -> None:
        with self._lock:
            job.counts = counts

    def provide_answer(self, job_id: str, answer: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)
            if job.status != "waiting_input":
                raise JobNotWaitingError(job_id)
            job._answer_value = answer
            job._answer_event.set()

    def request_cancel(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)
            if job.status not in ("running", "waiting_input"):
                raise JobNotCancellableError(job_id)
            job._cancel_requested = True
            # Unblock a worker blocked in wait_for_answer(); it notices the
            # cancel flag when it wakes up and raises OperationCancelled.
            job._answer_event.set()

    def cancel_requested(self, job: Job) -> bool:
        with self._lock:
            return job._cancel_requested

    def run_in_background(self, job: Job, target: Callable[[], object]) -> None:
        threading.Thread(target=self._run, args=(job, target), daemon=True).start()

    def _run(self, job: Job, target: Callable[[], object]) -> None:
        try:
            result = target()
        except OperationCancelled:
            with self._lock:
                job.status = "cancelled"
                job.pending = None
        except Exception as exc:
            with self._lock:
                job.error = str(exc)
                job.status = "error"
        else:
            with self._lock:
                job.result = result
                job.status = "done"
