"""Image facts produced by Gemini vs the Phase 1 manual transcriptions (test fixtures only — never pipeline input)."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from evidence import activity, images  # noqa: E402
from evidence.common import load_manifest  # noqa: E402

# file_id → {resolved resource_id: (category, state, identifier that must be present or None)}
EXPECTED = {
    "evidence_04": {"account_5762": ("USER_PROFILE", "PRESENT", ("email", "haruka.s1838@zoho.com"))},
    "evidence_09": {"search_428": ("SEARCH_INDEX_ENTRY", "PRESENT", ("user", "user_13")),
                    "search_1874": ("SEARCH_INDEX_ENTRY", "PRESENT", ("email", "g.silva76.jr@gmail.com"))},
    "evidence_14": {"data_flow_1121": ("DATA_FLOW", "FLOW_ACTIVE", ("email", "jain.aditi@gmail.com"))},
    "evidence_19": {"analytics_7438": ("ANALYTICS_PROFILE", "IDENTIFIABLE", ("user", "user_20"))},
    "evidence_23": {"export_1260": ("USER_EXPORT", "PRESENT", ("email", "ingrid.dahl@outlook.com"))},
    "evidence_28": {"support_1034": ("SUPPORT_MESSAGE", "IDENTIFIABLE", ("email", "kagyeman8947@fastmail.com"))},
    "evidence_32": {"backup_9287": ("BACKUP_ARCHIVE", "RESTORE_ALLOWED", ("email", "areed1433@gmail.com"))},
    "evidence_37": {"audit_record_003": ("SECURITY_AUDIT_LOG", "PRESENT", ("user", "user_03"))},
    "evidence_42": {"tombstone_17": ("ACCOUNT_TOMBSTONE", "REDACTED", None)},
    "evidence_46": {"object_19": ("SUPPORT_ATTACHMENT", "PRESENT", None)},
    "evidence_60": {"marketing_001": ("MARKETING_PROFILE", "PRESENT", ("email", "sj.park@naver.com"))},
}


@pytest.fixture(scope="module")
def observations():
    manifest = load_manifest(ROOT / "dataset")
    links = activity.catalog_links(activity.load_activities(ROOT / "dataset"))
    obs, missing = images.load(manifest, links=links)
    return obs, missing


def test_all_images_have_facts(observations):
    assert observations[1] == []


@pytest.mark.parametrize("file_id", sorted(EXPECTED))
def test_facts_match_manual_transcription(observations, file_id):
    got = {o.resource_id: o for o in observations[0] if o.evidence_id == file_id}
    for rid, (category, state, key) in EXPECTED[file_id].items():
        assert rid in got, f"{file_id}: {rid} not extracted"
        o = got[rid]
        assert (o.category.value, o.state.value) == (category, state)
        assert key is None or key in o.link_keys


def test_facts_files_record_model_and_prompt_version():
    for path in sorted(images.FACTS_DIR.glob("*.json")):
        facts = json.loads(path.read_text(encoding="utf-8"))
        assert facts["model"] and facts["prompt_version"] == "image_facts/v2"
