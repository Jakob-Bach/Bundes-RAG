import threading
import time

import pytest

from bundesrag.web.jobs import JobManager, JobNotFoundError, JobNotWaitingError
from bundesrag.web.schemas import PendingInputResponse


@pytest.fixture
def manager():
    return JobManager()


def _wait_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.01)
    pytest.fail("timed out waiting for condition")


def test_create_job_returns_running_job_with_unique_id(manager):
    first = manager.create_job()
    second = manager.create_job()

    assert first.status == "running"
    assert first.id != second.id
    assert manager.get(first.id) is first


def test_get_unknown_job_returns_none(manager):
    assert manager.get("unknown") is None


def test_run_in_background_stores_result_on_success(manager):
    job = manager.create_job()

    manager.run_in_background(job, lambda: "the result")

    _wait_until(lambda: job.status == "done")
    assert job.result == "the result"
    assert job.error is None


def test_run_in_background_stores_error_on_exception(manager):
    job = manager.create_job()

    def failing():
        raise RuntimeError("boom")

    manager.run_in_background(job, failing)

    _wait_until(lambda: job.status == "error")
    assert job.error == "boom"
    assert job.result is None


def test_wait_for_answer_round_trip(manager):
    job = manager.create_job()
    pending = PendingInputResponse(kind="ask_user", question="Welche Wahlperiode?")
    received = []

    def worker():
        received.append(manager.wait_for_answer(job, pending))

    thread = threading.Thread(target=worker)
    thread.start()
    _wait_until(lambda: job.status == "waiting_input")
    assert job.pending == pending

    manager.provide_answer(job.id, "die 21.")
    thread.join(timeout=5.0)

    assert not thread.is_alive()
    assert received == ["die 21."]
    assert job.status == "running"
    assert job.pending is None


def test_wait_for_answer_supports_multiple_rounds(manager):
    job = manager.create_job()
    received = []

    def worker():
        for round_number in (1, 2):
            pending = PendingInputResponse(kind="ask_user", question=f"Frage {round_number}")
            received.append(manager.wait_for_answer(job, pending))

    thread = threading.Thread(target=worker)
    thread.start()
    for round_number in (1, 2):
        _wait_until(
            lambda n=round_number: (
                job.status == "waiting_input"
                and job.pending is not None
                and job.pending.question == f"Frage {n}"
            )
        )
        manager.provide_answer(job.id, f"Antwort {round_number}")
    thread.join(timeout=5.0)

    assert received == ["Antwort 1", "Antwort 2"]


def test_set_progress_updates_job_progress(manager):
    job = manager.create_job()
    assert job.progress is None

    manager.set_progress(job, 0, 5)
    assert job.progress.current == 0
    assert job.progress.total == 5

    manager.set_progress(job, 3, 5)
    assert job.progress.current == 3
    assert job.progress.total == 5


def test_provide_answer_for_unknown_job_raises(manager):
    with pytest.raises(JobNotFoundError):
        manager.provide_answer("unknown", "answer")


def test_provide_answer_for_job_not_waiting_raises(manager):
    job = manager.create_job()

    with pytest.raises(JobNotWaitingError):
        manager.provide_answer(job.id, "answer")
