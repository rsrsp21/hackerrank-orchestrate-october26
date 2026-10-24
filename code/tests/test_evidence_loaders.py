"""Loader tests pinned to evidence rows established in Phase 1 (data_notes §2–§4, sample_walkthrough)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from evidence import activity, documents, logs, records, sql  # noqa: E402
from evidence.common import load_manifest  # noqa: E402
from evidence.model import Category, State  # noqa: E402
from identity import parse_ts, sha256_email  # noqa: E402


@pytest.fixture(scope="module")
def ev():
    manifest = load_manifest(ROOT / "dataset")
    so, sc = sql.load(manifest)
    ro, rc = records.load(manifest)
    acts = activity.load_activities(ROOT / "dataset")
    links = activity.catalog_links(acts)
    obs = so + ro + logs.load(manifest) + activity.observations(acts) + documents.load(manifest, links)
    return obs, sc + rc, links


def find(obs, rid, eid=None):
    return [o for o in obs if o.resource_id == rid and (eid is None or o.evidence_id == eid)]


def test_replica_drift_account_present(ev):
    (o,) = find(ev[0], "account_005", "evidence_54")
    assert (o.system_id, o.state, o.category) == ("account_service", State.PRESENT, Category.USER_PROFILE)
    assert ("email", "leila.haddad@yahoo.com") in o.link_keys


def test_topology_coverage_proves_absence(ev):
    (cov,) = [c for c in ev[1] if c.evidence_id == "evidence_54"]
    assert cov.proves_absent("account_001") and cov.proves_absent("account_004")
    assert not cov.proves_absent("account_005")
    assert not any(c.evidence_id == "evidence_90" for c in ev[1])  # inventory is never omission evidence


def test_empty_bundle_snapshot_is_coverage(ev):
    (cov,) = [c for c in ev[1] if c.evidence_id == "evidence_51"]
    assert cov.kind == "empty_snapshot" and cov.observed_at == parse_ts("2026-09-15T12:00:00Z")
    assert cov.proves_absent("account_4857")


def test_service_export_lookup_and_anonymized(ev):
    (o,) = find(ev[0], "account_6440", "evidence_92")
    assert o.state == State.ABSENT and o.observed_at == parse_ts("2026-09-15T09:31:19Z")
    (a,) = find(ev[0], "analytics_5335", "evidence_92")
    assert a.state == State.ANONYMIZED
    (p,) = find(ev[0], "account_5334", "evidence_92")
    assert p.state == State.PRESENT and ("email", "keiko.nakamura@gmail.com") in p.link_keys


def test_tombstones(ev):
    assert find(ev[0], "tombstone_9178", "evidence_51")[0].state == State.IDENTIFIABLE
    assert find(ev[0], "tombstone_440", "evidence_51")[0].state == State.REDACTED


def test_post_capture_trap_rows_keep_record_time(ev):
    rows = sorted(find(ev[0], "account_1417", "evidence_13"), key=lambda o: o.observed_at)
    assert [o.state for o in rows] == [State.ABSENT, State.PRESENT]
    audit = parse_ts("2026-08-12T09:00:00Z")
    assert rows[0].usable(audit) and not rows[1].usable(audit)


def test_log_trace_join_carries_lookup_key(ev):
    (o,) = find(ev[0], "account_9797", "evidence_01")
    assert o.state == State.ABSENT and ("email", "minjun.kim@gmail.com") in o.link_keys
    (c,) = find(ev[0], "analytics_9914", "evidence_01")
    old_hash = "44a65154bfd8e408852578fbd76813d094d1944f255ac1769ee81ba90492f10e"
    assert c.category == Category.CONTACT_RECORD and ("hash", old_hash) in c.link_keys
    assert any(o.state == State.RESTORE_ALLOWED for o in find(ev[0], "backup_3245", "evidence_01"))


def test_support_replica_marker_missing(ev):
    states = {o.state for o in find(ev[0], "support_002", "evidence_61")}
    assert states == {State.PRESENT}
    assert all(("email", "nadia.ionescu@yahoo.com") in o.link_keys for o in find(ev[0], "support_002", "evidence_61"))


def test_handover_ledger_states(ev):
    obs = ev[0]
    assert find(obs, "backup_3870", "evidence_03")[0].state == State.RESTORE_ALLOWED
    assert find(obs, "data_flow_9522", "evidence_03")[0].state == State.FLOW_ACTIVE
    (att,) = find(obs, "support_4218", "evidence_03")
    assert (att.category, att.state) == (Category.SUPPORT_ATTACHMENT, State.PRESENT)
    assert find(obs, "analytics_6830", "evidence_03")[0].state == State.ANONYMIZED


def test_inventory_backup_with_uppercase_email(ev):
    (o,) = find(ev[0], "backup_4978", "evidence_93")
    assert o.state == State.RESTORE_ALLOWED and ("email", "k.appiah88@gmail.com") in o.link_keys


def test_search_reference_to_account(ev):
    (o,) = find(ev[0], "search_001", "evidence_57")
    assert "account_006" in o.refs


def test_activity_signals_and_catalog(ev):
    obs, _, links = ev
    assert any(o.evidence_id == "activity_3387" and o.state == State.PRESENT for o in find(obs, "search_4882"))
    assert any(o.evidence_id == "activity_3709" and o.state == State.RESTORE_ALLOWED for o in find(obs, "backup_4978"))
    by_rid = {l.resource_id: l for l in links}
    assert by_rid["object_19"].exclusive and by_rid["object_19"].user_id == "user_07"
    assert by_rid["export_1842"].label == "NST-2026-0718-1842"


def test_documents(ev):
    (att,) = find(ev[0], "support_001", "evidence_58")
    assert att.category == Category.SUPPORT_ATTACHMENT and ("email", "priya.raman@gmail.com") in att.link_keys
    (stmt,) = find(ev[0], "export_1842", "evidence_18")
    assert stmt.category == Category.USER_EXPORT and ("user", "user_18") in stmt.link_keys
    assert not find(ev[0], "legal_hold_4118")  # the register names orders, not resources


def test_hash_link_from_email_hash_field(ev):
    h = sha256_email("minjun.jung@outlook.com")
    assert any(("hash", h) in o.link_keys for o in find(ev[0], "analytics_1792", "evidence_38"))
