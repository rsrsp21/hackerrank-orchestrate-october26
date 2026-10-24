"""Tests for the evaluation harness mechanics (code/evaluation/main.py, custom_cases.py)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code" / "evaluation"))

from custom_cases import CUSTOM_CASES  # noqa: E402
from evidence.index import build  # noqa: E402
from investigate import load_requests  # noqa: E402
from harness import DATA, run_custom  # noqa: E402
from score import load_answers  # noqa: E402


@pytest.fixture(scope="module")
def ctx():
    return load_requests(DATA), load_answers(DATA / "sample_output.csv"), build(DATA)


def test_case_definitions_are_well_formed(ctx):
    requests, samples, _ = ctx
    ids = [c["id"] for c in CUSTOM_CASES]
    assert len(ids) == len(set(ids)) >= 3
    known = {r["case_id"] for r in requests}
    for c in CUSTOM_CASES:
        assert "unit_tests" in c or c["source"] in known
        assert c.get("exact_from") is None or c["exact_from"] in samples


def test_wrong_expectations_are_reported(ctx):
    requests, samples, index = ctx
    base = next(c for c in CUSTOM_CASES if c["id"] == "cc_10")
    wrong_status = dict(base, status="COMPLETE")
    ok, status, _, problems = run_custom(wrong_status, requests, samples, index)
    assert not ok and status == "INCOMPLETE" and any("status" in p for p in problems)
    forbid = dict(base, must_not=[{"resource_id": "account_3866"}])
    ok, _, _, problems = run_custom(forbid, requests, samples, index)
    assert not ok and any("forbidden" in p for p in problems)
    missing = dict(base, must_contain=[{"resource_id": "account_does_not_exist"}])
    assert not run_custom(missing, requests, samples, index)[0]


def test_variant_changes_only_named_fields(ctx):
    requests, samples, index = ctx
    unchanged = {"id": "cc_x", "title": "no-op variant", "source": "case_21", "changes": {}, "exact_from": "case_21"}
    assert run_custom(unchanged, requests, samples, index)[0]
