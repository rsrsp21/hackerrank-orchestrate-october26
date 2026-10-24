"""Tests for code/evidence/model.py."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from evidence.model import (  # noqa: E402
    Category,
    Coverage,
    Directness,
    Observation,
    State,
    link_keys_from,
    resource_refs_from,
    system_for,
)
from identity import parse_ts, sha256_email  # noqa: E402

T = parse_ts


def _obs(cap, seen):
    return Observation("evidence_x", T(cap), T(seen), "account_service", "account_1", Category.USER_PROFILE, State.PRESENT)


def test_two_clock_rule_with_equality():
    audit = T("2026-08-12T09:00:00Z")
    assert _obs("2026-08-12T09:00:00Z", "2026-08-12T09:00:00Z").usable(audit)
    assert not _obs("2026-08-12T09:00:00Z", "2026-08-14T09:00:00Z").usable(audit)  # evidence_13 trap row
    assert not _obs("2026-09-18T11:55:24Z", "2026-09-16T08:57:00Z").usable(T("2026-09-16T09:00:00Z"))  # case_09 / evidence_06


def test_link_keys_nested_free_text_case_hash_phone():
    h = sha256_email("a.b@example.com")
    record = {
        "document": {"email": "O.ERIKSEN10@YAHOO.COM", "customer_reference": "user_403"},
        "message_text": "Please send the delivery update to A.B@Example.com. The order includes: lamp.",
        "correlation_key": h,
        "owner_phone": "+55 11 96656-0765",
        "subject_reference": None,
    }
    keys = link_keys_from(record)
    assert ("email", "o.eriksen10@yahoo.com") in keys
    assert ("email", "a.b@example.com") in keys
    assert ("user", "user_403") in keys
    assert ("hash", h) in keys
    assert ("phone", "5511966560765") in keys


def test_integrity_seal_is_not_a_hash_link():
    assert not any(k == "hash" for k, _ in link_keys_from({"integrity_seal": "sha256:" + "0" * 61 + "58d"}))


def test_resource_refs_and_system_mapping():
    assert resource_refs_from({"source_resource_id": "account_006"}, exclude="search_001") == {"account_006"}
    assert resource_refs_from("Restore job repopulated downstream resource search_4882.", exclude="backup_9287") == {"search_4882"}
    assert system_for("data_flow_9522") == "integration_service"
    assert system_for("audit_record_003") == "security_service"
    assert system_for("tombstone_440") == "identity_service"
    assert system_for("cache_1") is None  # never emitted (activity-only system)


def test_coverage_proves_absence_only_for_its_system():
    cov = Coverage("evidence_54", T("2026-09-02T23:00:00Z"), T("2026-09-02T23:00:00Z"), "account_service",
                   frozenset({"account_005", "account_8741"}), "topology_table")
    assert cov.proves_absent("account_004")
    assert not cov.proves_absent("account_005")
    assert not cov.proves_absent("search_001")
    assert Directness.OMISSION.value == "OMISSION"
