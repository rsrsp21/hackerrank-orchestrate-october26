"""Tests for code/evidence/images.py, code/evidence/index.py, and code/linking.py (tasks 4.3–4.5)."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from evidence import images  # noqa: E402
from evidence.common import load_manifest  # noqa: E402
from evidence.index import build  # noqa: E402
from evidence.model import Category, Directness, State  # noqa: E402
from identity import IdentityResolver, load_identity_tables, parse_ts  # noqa: E402
from linking import identifier_links  # noqa: E402

T = parse_ts


@pytest.fixture(scope="module")
def idx():
    return build(ROOT / "dataset")


@pytest.fixture(scope="module")
def resolver():
    return IdentityResolver(*load_identity_tables(ROOT / "dataset"))


# ---- 4.3 image facts interface -------------------------------------------------------------

def test_image_facts_conversion_and_validation(tmp_path):
    manifest = load_manifest(ROOT / "dataset")
    (tmp_path / "evidence_04.json").write_text(json.dumps({"file_id": "evidence_04", "records": [
        {"resource_id": "account_5762", "category": "USER_PROFILE", "state": "PRESENT",
         "emails": ["Haruka.S1838@zoho.com"], "phones": ["+81 90 7610 2507"], "user_ids": ["user_11"],
         "references": ["support_9538"]},
        {"resource_id": "not a resource", "category": "USER_PROFILE", "state": "PRESENT"},
        {"resource_id": "account_1", "category": "BOGUS", "state": "PRESENT"},
    ]}), encoding="utf-8")
    obs, missing = images.load(manifest, tmp_path)
    assert len(missing) == 10 and "evidence_04" not in missing
    (o,) = obs
    assert (o.system_id, o.category, o.state) == ("account_service", Category.USER_PROFILE, State.PRESENT)
    assert {("email", "haruka.s1838@zoho.com"), ("phone", "819076102507"), ("user", "user_11")} <= o.link_keys
    assert o.refs == {"support_9538"} and o.observed_at == o.file_captured_at == T("2026-09-26T11:00:00Z")


def test_images_only_enter_through_facts_files(idx):
    image_ids = {"evidence_04", "evidence_09", "evidence_14", "evidence_19", "evidence_23", "evidence_28",
                 "evidence_32", "evidence_37", "evidence_42", "evidence_46", "evidence_60"}
    from_images = [o for o in idx.observations if o.evidence_id in image_ids]
    assert all(o.source.endswith(":image_facts") for o in from_images)
    assert set(idx.missing_image_facts) | {o.evidence_id for o in from_images} == image_ids


# ---- 4.4 index: two clocks, request window, direct over omission -----------------------------

def test_direct_beats_later_omission(idx):
    o = idx.state_at("account_6440", T("2026-09-15T12:00:00Z"), T("2026-09-04T12:00:00Z"))
    assert (o.evidence_id, o.state, o.directness) == ("evidence_92", State.ABSENT, Directness.DIRECT)


def test_omission_latest_qualifying_coverage(idx):
    o = idx.state_at("account_004", T("2026-09-07T10:20:00Z"), T("2026-08-25T12:32:00Z"))
    assert (o.evidence_id, o.directness) == ("evidence_54", Directness.OMISSION)  # not inventory evidence_90
    o = idx.state_at("account_4857", T("2026-09-15T12:00:00Z"), T("2026-09-04T12:00:00Z"))
    assert o.evidence_id == "evidence_51"


def test_trap_row_after_capture_is_ignored(idx):
    o = idx.state_at("account_1417", T("2026-08-12T09:00:00Z"))
    assert o.state == State.ABSENT and o.evidence_id == "evidence_13"


def test_post_audit_file_excluded_case_09(idx):
    o = idx.state_at("backup_4978", T("2026-09-16T09:00:00Z"), T("2026-09-05T09:00:00Z"))
    assert (o.evidence_id, o.state) == ("evidence_93", State.RESTORE_ALLOWED)  # evidence_06 is captured 09-18


def test_recreation_after_audit_ignored_case_27(idx):
    o = idx.state_at("account_3866", T("2026-09-15T12:00:00Z"), T("2026-08-29T12:00:00Z"))
    assert (o.evidence_id, o.state) == ("evidence_92", State.ABSENT)


def test_request_window_drops_earlier_episode(idx):
    # account_6523 was observed 404 on 03-10 for an earlier request of the same subject (case_46): that direct
    # observation is outside case_17's window; only the in-window omission proof (empty snapshot) remains
    o = idx.state_at("account_6523", T("2026-09-15T12:00:00Z"), T("2026-08-19T12:00:00Z"))
    assert (o.evidence_id, o.directness) == ("evidence_51", Directness.OMISSION)
    assert not idx.usable("account_6523", T("2026-09-15T12:00:00Z"), T("2026-08-19T12:00:00Z"))
    assert idx.state_at("account_6523", T("2026-03-11T08:00:00Z"), T("2026-03-09T00:00:00Z")).evidence_id == "evidence_67"


# ---- 4.5 identifier links (L1–L4) ------------------------------------------------------------

def _links(resolver, idx, email, audit, horizon="audit"):
    s = resolver.resolve(email, T(audit))
    return identifier_links(s, idx, T(audit) if horizon == "audit" else None)


def test_reference_link_search_to_account(resolver, idx):
    links = _links(resolver, idx, "jonas.berg@outlook.com", "2026-09-10T09:15:00Z")
    assert links["search_001"].kind == "L1" and links["account_006"].kind == "L3"
    assert "search_8814" not in links and "search_4203" not in links  # Berglund / Joana Berg decoys


def test_old_hash_and_old_email_links(resolver, idx):
    assert "analytics_9914" in _links(resolver, idx, "minjun.kim@gmail.com", "2026-09-15T12:00:00Z")
    links = _links(resolver, idx, "nadia.ionescu@yahoo.com", "2026-09-18T12:25:00Z")
    assert "support_002" in links and "support_5914" not in links  # nadia.popescu decoy


def test_similar_email_decoy_case_28(resolver, idx):
    assert "search_8168" not in _links(resolver, idx, "smartinez6461@gmail.com", "2026-09-15T12:00:00Z", horizon=None)


def test_catalog_link_and_membership_horizon(resolver, idx):
    links = _links(resolver, idx, "haruka.s1838@zoho.com", "2026-09-27T13:00:00Z")
    assert links["account_5762"].kind in ("L1", "L4")
    strict = _links(resolver, idx, "thandiwe.m6866@zoho.com", "2026-09-15T12:00:00Z")
    loose = _links(resolver, idx, "thandiwe.m6866@zoho.com", "2026-09-15T12:00:00Z", horizon=None)
    assert "audit_record_4128" not in strict and "audit_record_4128" in loose  # only in post-audit evidence_02
