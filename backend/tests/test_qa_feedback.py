"""Feedback-driven QA retry: the failure reason becomes the next attempt's instruction.

The blind-retry gap was that a failed generation was simply re-run with the identical prompt.
These tests pin the fix: each failed check produces a specific, imperative correction, the
corrections aggregate across a batch, and the whole thing is expressed in the Genblaze
`EvaluationResult` vocabulary the SDK's AgentLoop refines on.
"""
from __future__ import annotations

import pytest

from originshot_pipelines import qa


def _report(passed: bool, checks: list[dict], vlm_score=None) -> dict:
    return {"passed": passed, "checks": checks, "scorer": "deterministic",
            "vlm_score": vlm_score, "vlm_verdict": None}


def test_each_failed_check_becomes_an_actionable_instruction():
    report = _report(False, [
        {"name": "white_background", "passed": False, "value": 0.62, "threshold": 0.90},
        {"name": "product_match", "passed": False, "value": 3, "threshold": 6},
    ])
    fb = qa.feedback_from_report(report)
    # Names the actual problem and the measured numbers, not a vague "try again".
    assert "background" in fb and "0.62" in fb
    assert "same physical product" in fb.lower() and "3/10" in fb


def test_passing_checks_contribute_no_feedback():
    report = _report(True, [
        {"name": "white_background", "passed": True, "value": 0.99, "threshold": 0.90},
        {"name": "resolution", "passed": True, "value": "1024x1024", "threshold": "..."},
    ])
    assert qa.feedback_from_report(report) == ""


def test_batch_feedback_is_the_deduplicated_union():
    """A four-scene style is retried whole, so it gets each distinct failure named once."""
    r1 = _report(False, [{"name": "product_match", "passed": False, "value": 2, "threshold": 6}])
    r2 = _report(False, [{"name": "product_match", "passed": False, "value": 4, "threshold": 6},
                         {"name": "resolution", "passed": False, "value": "300x300",
                          "threshold": "short side >= 512px"}])
    r3 = _report(True, [{"name": "resolution", "passed": True, "value": "1024", "threshold": "x"}])

    fb = qa.feedback_from_reports([r1, r2, r3])
    # product_match appears once despite two failures; resolution appears once; passing r3 adds nothing.
    assert fb.lower().count("same physical product") == 1
    assert "resolution" in fb.lower()


def test_no_failures_no_feedback():
    assert qa.feedback_from_reports([_report(True, [])]) == ""


# ── Genblaze EvaluationResult vocabulary ───────────────────────────────
def test_report_becomes_a_genblaze_evaluation_result():
    pytest.importorskip("genblaze_core")
    from genblaze_core.agents import EvaluationResult

    report = _report(False, [
        {"name": "white_background", "passed": False, "value": 0.5, "threshold": 0.9},
    ], vlm_score=4)
    ev = qa.to_evaluation(report)
    assert isinstance(ev, EvaluationResult)
    assert ev.passed is False
    assert ev.score == pytest.approx(0.4)          # vlm_score / 10
    assert ev.feedback and "background" in ev.feedback  # the refinement AgentLoop would read
    assert ev.metadata["scorer"] == "deterministic"


def test_passing_evaluation_carries_no_feedback():
    pytest.importorskip("genblaze_core")
    report = _report(True, [{"name": "resolution", "passed": True, "value": "1024", "threshold": "x"}])
    ev = qa.to_evaluation(report)
    assert ev.passed is True
    assert ev.feedback is None


# ── The retry actually splices feedback into the prompt ────────────────
def test_with_feedback_appends_correction_to_prompt():
    from originshot_pipelines.providers import with_feedback

    base = "Professional e-commerce product photograph of a mug."
    assert with_feedback(base, None) == base            # first attempt untouched
    out = with_feedback(base, "the background was not pure white")
    assert out.startswith(base)
    assert "Correct these issues" in out and "pure white" in out


def test_studio_request_carries_feedback_into_the_prompt():
    pytest.importorskip("genblaze_core")
    from originshot_pipelines.studio import studio_request

    req = studio_request("https://x/a.png", "a blue mug",
                         feedback="preserve the exact colour of the reference product")
    assert "preserve the exact colour" in req.prompt
    assert "Correct these issues" in req.prompt
