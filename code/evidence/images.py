"""Screenshot evidence → Observations, via structured image facts.

Images are not parsed here. A vision extractor (Phase 7, Gemini) writes one facts file per image to
`code/llm_cache/image_facts/<file_id>.json`. That folder is committed and shipped so a run without an API
key reproduces the same output. This module only validates those facts and converts them; when a facts file
is missing, the image contributes nothing (never a hand transcription).

Facts schema (one file per image):
{
  "file_id": "evidence_04",
  "model": "<vision model id>",
  "records": [
    {
      "resource_id": "account_5762",          # as printed on screen ("" when the screen shows no resource id)
      "labels": ["CS-8538"],                  # other printed references (file names, ticket/statement numbers,
                                              # bare user ids); resolved to a resource via data-catalog links
      "category": "USER_PROFILE",             # a Category value
      "state": "PRESENT",                     # a State value
      "emails": ["..."], "phones": ["..."], "user_ids": ["user_11"],
      "references": ["support_9538"],         # other resource ids shown as linked
      "observed_at": "2026-09-26T11:00:00Z"   # optional; defaults to the file's captured_at
    }
  ]
}
"""

import json
import re
from pathlib import Path

from evidence.common import files_under
from evidence.model import RESOURCE_RE, Category, Observation, State, system_for
from identity import norm_email, norm_phone, parse_ts

FACTS_DIR = Path(__file__).resolve().parents[1] / "llm_cache" / "image_facts"


def facts_path(file_id, facts_dir=FACTS_DIR):
    return Path(facts_dir) / f"{file_id}.json"


def _resolve(rec, links):
    rid = (rec.get("resource_id") or "").strip()
    if RESOURCE_RE.fullmatch(rid):
        return rid
    labels = {str(x).strip() for x in rec.get("labels", []) if x} | ({rid} if rid else set())
    hits = sorted({link.resource_id for link in links if link.label in labels and link.label != link.resource_id})
    return hits[0] if len(hits) == 1 else None


def _record_observation(ef, rec, links=()):
    rid = _resolve(rec, links)
    if rid is None:
        return None
    try:
        category, state = Category(rec["category"]), State(rec["state"])
    except (KeyError, ValueError):
        return None
    keys = {("email", norm_email(e)) for e in rec.get("emails", []) if e}
    keys |= {("phone", norm_phone(p)) for p in rec.get("phones", []) if norm_phone(p)}
    keys |= {("user", u) for u in rec.get("user_ids", []) if re.fullmatch(r"user_\d+", u or "")}
    refs = {r for r in rec.get("references", []) if RESOURCE_RE.fullmatch(r or "") and r != rid}
    seen = parse_ts(rec["observed_at"]) if rec.get("observed_at") else ef.captured_at
    return Observation(ef.file_id, ef.captured_at, min(seen, ef.captured_at), system_for(rid) or "", rid, category,
                       state, frozenset(keys), frozenset(refs), source=f"{ef.path.name}:image_facts")


def load(manifest, facts_dir=FACTS_DIR, links=()):
    observations, missing = [], []
    for ef in files_under(manifest, "images", {".png", ".jpg", ".jpeg"}):
        path = facts_path(ef.file_id, facts_dir)
        if not path.exists():
            missing.append(ef.file_id)
            continue
        facts = json.loads(path.read_text(encoding="utf-8"))
        for rec in facts.get("records", []):
            obs = _record_observation(ef, rec, links)
            if obs:
                observations.append(obs)
    return observations, missing
