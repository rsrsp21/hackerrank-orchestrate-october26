"""Tests for code/evaluation/score.py (task 5.3)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code" / "evaluation"))

from score import score  # noqa: E402


def step(n, rid, op="VERIFY_RECORD_ABSENT", ev=""):
    return {"step_no": n, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": rid,
            "operation": op, "state": "ABSENT", "evidence_id": ev}


def test_perfect_match():
    exp = {"c1": ("COMPLETE", [step(1, "account_1", ev="e1")]), "c2": ("NOT_APPLICABLE", [])}
    m = score(exp, exp)
    assert m["status_accuracy"] == m["step_f1"] == m["sequence_exact"] == 1.0
    assert all(v == 1.0 for v in m["field_accuracy"].values())


def test_missing_wrong_and_key_order():
    exp = {"c1": ("INCOMPLETE", [step(1, "account_1"), step(2, "search_1")])}
    got = {"c1": ("INCOMPLETE", [dict(reversed(list(step(1, "account_1").items())))])}  # key order differs
    m = score(exp, got)
    assert m["step_precision"] == 1.0 and m["step_recall"] == 0.5
    assert m["sequence_exact"] == 0.0 and m["field_accuracy"]["resource_id"] == 0.5
    m = score(exp, {})
    assert m["status_accuracy"] == 0.0 and m["step_recall"] == 0.0
