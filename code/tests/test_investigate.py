"""Tests for code/investigate.py (task 4.7) against the public samples' conventions."""

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from investigate import investigate_all  # noqa: E402

# Expected resources that cannot be derived from participant data (sample_walkthrough §3b), and the accepted tie.
UNREACHABLE = {"case_18": {"audit_record_6645"}, "case_20": {"audit_record_5569"}}
ACCEPTED_TIES = {"case_23"}


@pytest.fixture(scope="module")
def cases():
    return investigate_all(ROOT / "dataset")


@pytest.fixture(scope="module")
def expected():
    with open(ROOT / "dataset" / "sample_output.csv", newline="", encoding="utf-8") as f:
        return {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(f)}


def _resources(inv):
    return {inv.account.resource_id} | {x.resource_id for x in inv.resources}


def test_every_request_investigated(cases):
    assert len(cases) == 550
    assert sum(inv.status == "NOT_APPLICABLE" for inv in cases.values()) == 10


def test_sample_status(cases, expected):
    assert {c: cases[c].status for c in expected} == {c: s for c, (s, _) in expected.items()}


def test_sample_resource_sets(cases, expected):
    for cid, (_, steps) in expected.items():
        if cid in ACCEPTED_TIES:
            continue
        want = {s["resource_id"] for s in steps} - UNREACHABLE.get(cid, set())
        assert _resources(cases[cid]) == want, cid


def test_sample_cited_evidence(cases, expected):
    for cid, (_, steps) in expected.items():
        got = {cases[cid].account.resource_id: cases[cid].account.evidence_id}
        got.update({x.resource_id: x.evidence_id for x in cases[cid].resources})
        for s in steps:
            if s["evidence_id"]:
                assert got[s["resource_id"]] == s["evidence_id"], (cid, s["resource_id"])


def test_key_conventions(cases):
    assert cases["case_05"].account.action == "DELETE"                 # replica drift → finding (C12)
    assert cases["case_27"].account.compliant_state == "ABSENT"        # post-audit recreation ignored (C10)
    assert cases["case_31"].account.evidence_id == "evidence_51"       # empty snapshot omission (C14)
    assert cases["case_04"].account.link.startswith("L6")              # naming fallback, flagged
    tomb = {x.resource_id: x for x in cases["case_32"].resources}["tombstone_9178"]
    assert tomb.action == "REDACT"                                     # tombstone redacted, never deleted (C19)
    assert all(x.action != "DELETE" for inv in cases.values() for x in inv.resources
               if x.category and x.category.value in ("SECURITY_AUDIT_LOG", "LEGAL_HOLD_RECORD", "BACKUP_ARCHIVE"))


def test_deterministic(cases):
    again = investigate_all(ROOT / "dataset")
    snap = lambda cs: {c: (i.status, i.account, tuple(i.resources)) for c, i in cs.items()}  # noqa: E731
    assert snap(again) == snap(cases)



def test_catalog_link_rejected_when_record_names_someone_else():
    """Q9 rule: a catalog-only link is dropped when the record's own identifiers belong to another person."""
    from types import SimpleNamespace

    from investigate import identity_conflict

    subject = SimpleNamespace(link_keys=lambda: frozenset({("user", "user_09"), ("email", "kwame-mensah@proton.me")}))
    other = SimpleNamespace(link_keys=frozenset({("email", "sj.park@naver.com"), ("phone", "821058379451")}))
    own = SimpleNamespace(link_keys=frozenset({("email", "kwame-mensah@proton.me")}))
    blank = SimpleNamespace(link_keys=frozenset())
    index = SimpleNamespace(by_rid={"marketing_001": [other], "marketing_002": [own], "marketing_003": [blank]})
    assert identity_conflict(index, "marketing_001", subject)
    assert not identity_conflict(index, "marketing_002", subject)
    assert not identity_conflict(index, "marketing_003", subject)  # no direct identifiers → cannot contradict
