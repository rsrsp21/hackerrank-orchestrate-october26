"""Tests for code/policy.py (task 5.2): operations, ordering, evidence rules, serialization."""

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from evidence.model import Category  # noqa: E402
from investigate import CaseInvestigation, ResourceState, investigate_all  # noqa: E402
from policy import ALLOWED, FINDING, PHASES, REMEDIATION, VERIFICATION, _sort_key, serialize, steps_for  # noqa: E402

KNOWN_DIFFS = {"case_18", "case_20", "case_23"}  # unreachable audit records + accepted tie (sample_walkthrough §3b)


def rs(rid, system, action, evidence="", compliant="", category=None):
    return ResourceState(system, rid, category, None, evidence, "L1", action, compliant)


def inv(account, *resources, intent="DELETION"):
    i = CaseInvestigation("case_x", intent)
    i.account, i.resources = account, list(resources)
    return i


@pytest.fixture(scope="module")
def cases():
    return investigate_all(ROOT / "dataset")


@pytest.fixture(scope="module")
def expected():
    with open(ROOT / "dataset" / "sample_output.csv", newline="", encoding="utf-8") as f:
        return {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(f)}


def test_allowed_pairs_match_problem_statement():
    assert len(ALLOWED) == 15
    assert ALLOWED[(FINDING, "REPORT_RESTORE_RISK")] == "ACTIVE"
    assert ALLOWED[(VERIFICATION, "VERIFY_RECORD_PRESENT")] == "PRESENT"


def test_not_applicable_is_empty():
    assert steps_for(inv(None, intent="NOT_APPLICABLE")) == []


def test_incomplete_structure_and_evidence():
    case = inv(rs("account_1", "account_service", "NONE", "ev_a", "ABSENT"),
               rs("search_1", "search_service", "DELETE", "ev_s"),
               rs("data_flow_1", "integration_service", "DISABLE", "ev_f"),
               rs("audit_record_1", "security_service", "RETAIN", "ev_r", "PRESENT", Category.SECURITY_AUDIT_LOG))
    steps = steps_for(case)
    assert [s["step_no"] for s in steps] == list(range(1, len(steps) + 1))
    assert [s["phase"] for s in steps] == sorted((s["phase"] for s in steps), key=PHASES.index)
    findings = [s for s in steps if s["phase"] == FINDING]
    assert [(s["operation"], s["evidence_id"]) for s in findings] == [("REPORT_REMAINING_RECORD", "ev_s"),
                                                                      ("REPORT_ACTIVE_DATA_FLOW", "ev_f")]
    assert all(s["evidence_id"] == "" for s in steps if s["phase"] != FINDING)
    rem = [s["operation"] for s in steps if s["phase"] == REMEDIATION]
    assert rem == ["DISABLE_DATA_FLOW", "DELETE_RECORD"]  # stop the flow before deleting
    ver = [(s["operation"], s["resource_id"]) for s in steps if s["phase"] == VERIFICATION]
    assert ver == [("VERIFY_RECORD_ABSENT", "account_1"), ("VERIFY_RECORD_ABSENT", "search_1"),
                   ("VERIFY_RECORD_PRESENT", "audit_record_1"), ("VERIFY_DATA_FLOW_DISABLED", "data_flow_1")]


def test_account_finding_is_not_duplicated():
    steps = steps_for(inv(rs("account_5", "account_service", "DELETE", "ev")))
    assert [(s["phase"], s["operation"]) for s in steps] == [
        (FINDING, "REPORT_REMAINING_RECORD"), (REMEDIATION, "DELETE_RECORD"), (VERIFICATION, "VERIFY_RECORD_ABSENT")]


def test_complete_is_verification_only_with_evidence():
    case = inv(rs("account_1", "account_service", "NONE", "ev_a", "ABSENT"),
               rs("analytics_1", "analytics_platform", "NONE", "ev_n", "ANONYMIZED"),
               rs("tombstone_1", "identity_service", "NONE", "ev_t", "REDACTED"))
    steps = steps_for(case)
    assert {s["phase"] for s in steps} == {VERIFICATION}
    assert all(s["evidence_id"] for s in steps)
    assert [s["operation"] for s in steps] == ["VERIFY_RECORD_ABSENT", "VERIFY_RECORD_REDACTED", "VERIFY_RECORD_ANONYMIZED"]


def test_every_emitted_pair_is_allowed_and_sorted(cases):
    for c in cases.values():
        steps = steps_for(c)
        assert all(ALLOWED[(s["phase"], s["operation"])] == s["state"] for s in steps)
        assert steps == sorted(steps, key=_sort_key)


def test_samples_sequence_exact(cases, expected):
    exact = {c for c, (_, steps) in expected.items() if steps_for(cases[c]) == steps}
    assert set(expected) - exact == KNOWN_DIFFS


def test_serialization_is_compact_sorted_and_round_trips():
    steps = steps_for(inv(rs("account_1", "account_service", "NONE", "ev", "ABSENT")))
    text = serialize(steps)
    assert text.startswith('[{"evidence_id":"ev","operation":"VERIFY_RECORD_ABSENT","phase":"VERIFICATION"')
    assert " " not in text and json.loads(text) == steps
