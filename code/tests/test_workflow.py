"""Tests for code/workflow.py (task 4.6): joint workflow-timing assignment and fallbacks."""

import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from evidence.activity import Activity  # noqa: E402
from identity import parse_ts  # noqa: E402
from workflow import WorkflowRequest, assign_workflows  # noqa: E402

REP = parse_ts("2026-09-02T12:00:00Z")


def req(cid, user, status="NOT_STARTED", rep=REP):
    return WorkflowRequest(cid, user, rep - timedelta(days=2), rep, rep + timedelta(days=13), status)


def act(aid, minutes, rid, result="FAILED", etype="DELETE_RECORD", target="account_service", details=None):
    if details is None:
        details = f"Deletion worker submitted primary profile {rid} to {target}." if target == "account_service" \
            else f"Policy action completed for {rid}."
    return Activity(aid, REP + timedelta(minutes=minutes), etype, "deletion_worker", target, rid, result, details)


def test_status_result_match_and_elimination():
    requests = [req("c1", "user_25"), req("c2", "user_26"), req("c3", "user_30", status="COMPLETE")]
    acts = [act("a1", -72, "account_3136"), act("a2", -51, "account_5684"), act("a3", -70, "account_4842", "SUCCESS")]
    owners = {"account_5684": {"user_26"}}  # identifier-linked to c2's subject
    out = assign_workflows(requests, acts, owners)
    # account_5684 is removed up front (owned by user_26), so c1 is left with exactly one candidate
    assert (out["c1"]["account"].resource_id, out["c1"]["account"].method) == ("account_3136", "unique")
    assert (out["c2"]["account"].resource_id, out["c2"]["account"].method) == ("account_5684", "own-identifier")
    assert (out["c3"]["account"].resource_id, out["c3"]["account"].method) == ("account_4842", "unique")


def test_owned_by_other_subject_is_removed():
    out = assign_workflows([req("c1", "user_1")], [act("a1", -60, "account_9")], {"account_9": {"user_2"}})
    assert out["c1"]["account"].kind == "L6"  # no free candidate left → fallback


def test_tie_break_subject_order_and_template_offsets():
    requests = [req("c26", "user_26", "COMPLETE"), req("c25", "user_25", "COMPLETE")]
    acts = [act("x", -60, "account_1", "SUCCESS"), act("y", -59, "account_2", "SUCCESS"),
            act("p", -29, "analytics_1895", "SUCCESS", "ANONYMIZE_RECORD", "analytics_platform"),
            act("q", -29 + 0.3, "analytics_4566", "SUCCESS", "ANONYMIZE_RECORD", "analytics_platform"),
            act("late", +90, "analytics_7777", "SUCCESS", "ANONYMIZE_RECORD", "analytics_platform")]  # wrong offset
    out = assign_workflows(requests, acts, {})
    assert out["c25"]["analytics"].resource_id == "analytics_1895"
    assert out["c26"]["analytics"].resource_id == "analytics_4566"
    assert {out["c25"]["account"].method, out["c26"]["account"].method} == {"tie-break"}


def test_analytics_eligibility_and_window_evidence():
    requests = [req("c24", "user_24", "COMPLETE"), req("c25", "user_25", "COMPLETE")]
    acts = [act("p", -29, "analytics_1895", "SUCCESS", "ANONYMIZE_RECORD", "analytics_platform")]
    out = assign_workflows(requests, acts, {}, analytics_eligible={"c25"})
    assert out["c24"]["analytics"] is None and out["c25"]["analytics"].resource_id == "analytics_1895"
    out = assign_workflows(requests, acts, {}, has_window_evidence=lambda r, rid: False)
    assert out["c25"]["analytics"] is None


def test_account_fallback_chain():
    out = assign_workflows([req("c34", "user_11")], [], {"account_5762": {"user_11"}})
    assert (out["c34"]["account"].resource_id, out["c34"]["account"].method) == ("account_5762", "identifier-account")
    out = assign_workflows([req("c04", "user_04")], [], {})
    assert (out["c04"]["account"].resource_id, out["c04"]["account"].kind) == ("account_004", "L6")


def test_scenario_case_without_status_match_uses_any_result():
    out = assign_workflows([req("c06", "user_06", "PARTIALLY_COMPLETE")], [act("a", -4, "account_006", "SUCCESS")], {})
    assert out["c06"]["account"].resource_id == "account_006"
