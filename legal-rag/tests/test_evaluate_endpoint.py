"""Tests for the POST /evaluate background-job lifecycle in src/api/main.py.

Full end-to-end coverage of these routes would need the real embedding
model and a real Chroma index (built via the real build_services() in
FastAPI's lifespan), which is too heavy for a unit test. Instead this
exercises _run_evaluation_job directly against a stubbed
run_and_build_output/write_results, using a small object standing in for
the pieces of app.state these functions read/write - the same isolation
strategy tests/test_generation.py uses by stubbing LLMClient rather than
calling a real model.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from src.api import main as api_main


class _FakeSummary:
    pass


def _fake_run_and_build_output(*, app_dir, retrieval_method, chunking_method, top_k):
    return SimpleNamespace(
        summary=_FakeSummary(),
        output={
            "manifest": {"retrieval_method": retrieval_method, "chunking_method": chunking_method},
            "summary": {"overall": {"recall_at_5": 0.5}},
            "case_results": [],
        },
    )


def _fake_write_results(data_dir, output):
    return data_dir / "eval_runs" / "fake-run" / "results.json"


@pytest.fixture
def fake_app_state(monkeypatch):
    monkeypatch.setattr(api_main, "run_and_build_output", _fake_run_and_build_output)
    monkeypatch.setattr(api_main, "write_results", _fake_write_results)
    state = SimpleNamespace(eval_runs={}, eval_lock=threading.Lock())
    monkeypatch.setattr(api_main.app, "state", state)
    return state


def test_job_transitions_pending_to_done(fake_app_state):
    run_id = "test-run-1"
    fake_app_state.eval_runs[run_id] = {
        "run_id": run_id,
        "status": "pending",
        "retrieval_method": "hybrid",
        "chunking_method": "legal",
        "error": None,
        "results_path": None,
        "summary": None,
    }

    api_main._run_evaluation_job(run_id, "hybrid", "legal", 5)

    record = fake_app_state.eval_runs[run_id]
    assert record["status"] == "done"
    assert record["error"] is None
    assert record["summary"] == {"overall": {"recall_at_5": 0.5}}
    assert record["results_path"] is not None


def test_job_failure_is_recorded_not_raised(fake_app_state, monkeypatch):
    def _raise(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(api_main, "run_and_build_output", _raise)

    run_id = "test-run-2"
    fake_app_state.eval_runs[run_id] = {
        "run_id": run_id,
        "status": "pending",
        "retrieval_method": "hybrid",
        "chunking_method": "legal",
        "error": None,
        "results_path": None,
        "summary": None,
    }

    api_main._run_evaluation_job(run_id, "hybrid", "legal", 5)

    record = fake_app_state.eval_runs[run_id]
    assert record["status"] == "failed"
    assert "boom" in record["error"]


def test_lock_serializes_concurrent_jobs(fake_app_state):
    """Two jobs racing for the lock must not interleave - the second only
    starts once the first has fully finished, matching the single-writer
    constraint (never two evaluation runs touching data/eval_runs/ or a
    Chroma directory at the same time)."""
    order: list[str] = []
    original = api_main.run_and_build_output

    def _tracking_run(*, app_dir, retrieval_method, chunking_method, top_k):
        order.append(f"start-{retrieval_method}")
        result = _fake_run_and_build_output(
            app_dir=app_dir, retrieval_method=retrieval_method, chunking_method=chunking_method, top_k=top_k
        )
        order.append(f"end-{retrieval_method}")
        return result

    import src.api.main as m

    m.run_and_build_output = _tracking_run
    try:
        for run_id, method in [("run-a", "dense"), ("run-b", "bm25")]:
            fake_app_state.eval_runs[run_id] = {
                "run_id": run_id,
                "status": "pending",
                "retrieval_method": method,
                "chunking_method": "legal",
                "error": None,
                "results_path": None,
                "summary": None,
            }

        t1 = threading.Thread(target=m._run_evaluation_job, args=("run-a", "dense", "legal", 5))
        t2 = threading.Thread(target=m._run_evaluation_job, args=("run-b", "bm25", "legal", 5))
        t1.start()
        t1.join()
        t2.start()
        t2.join()
    finally:
        m.run_and_build_output = original

    assert order == ["start-dense", "end-dense", "start-bm25", "end-bm25"]


def test_unknown_run_id_status_lookup_returns_none(fake_app_state):
    assert fake_app_state.eval_runs.get("does-not-exist") is None
