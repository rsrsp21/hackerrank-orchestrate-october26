"""JSON / TXT record evidence → Observations and account Coverage.

Families (data_notes §3.2): snapshot bundles, service resource exports, ledgers, single-collection exports,
and the shift-handover text. Record-level times (snapshot captured_at, observed_at, recorded_at) are kept
as `observed_at` for the two-clock rule. An explicitly empty account_service snapshot inside a bundle is
account Coverage (sample case_31 cites evidence_51).
"""

import json

from evidence.common import files_under
from evidence.interpret import observe
from evidence.model import Coverage
from identity import parse_ts

SINGLE_COLLECTION_SYSTEM = {"customer_analytics_reports": "analytics_platform", "customer_export_jobs": "export_service"}


def _handover(ef, text):
    out = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.lstrip("- ").split("|")]
        if not line.startswith("- ") or len(parts) != 6:
            continue
        ts, system, rid, rtype, result, ident = parts
        record = {"resource_id": rid, "system": system, "record_type": rtype, "result": result,
                  "subject_reference": None if ident == "no direct identifier" else ident}
        ctx = dict(evidence_id=ef.file_id, file_captured_at=ef.captured_at, observed_at=parse_ts(ts),
                   source=f"{ef.path.name}:handover")
        out.extend(observe("handover_check", record, ctx))
    return out


def load(manifest):
    observations, coverages = [], []
    for ef in files_under(manifest, "records", {".json", ".txt"}):
        text = ef.path.read_text(encoding="utf-8")
        if ef.path.suffix == ".txt":
            observations.extend(_handover(ef, text))
            continue
        doc = json.loads(text)
        base = dict(evidence_id=ef.file_id, file_captured_at=ef.captured_at)
        if "snapshots" in doc:
            for snap in doc["snapshots"]:
                seen = parse_ts(snap["captured_at"])
                if not snap["records"] and snap["data_store"] == "account_service":
                    coverages.append(Coverage(ef.file_id, ef.captured_at, seen, "account_service", frozenset(),
                                              "empty_snapshot", f"{ef.path.name}:{snap['collection']}"))
                for rec in snap["records"]:
                    seen_rec = parse_ts(rec["recorded_at"]) if rec.get("recorded_at") else seen
                    ctx = dict(base, observed_at=seen_rec, source=f"{ef.path.name}:{snap['collection']}")
                    observations.extend(observe(snap["collection"], rec, ctx))
        elif "service_exports" in doc:
            for system, collections in doc["service_exports"].items():
                for collection, rows in collections.items():
                    for rec in rows:
                        ctx = dict(base, observed_at=parse_ts(rec["observed_at"]), system_hint=system,
                                   source=f"{ef.path.name}:{system}.{collection}")
                        observations.extend(observe(collection, rec, ctx))
        elif "record_count" in doc:
            for rec in doc["records"]:
                ctx = dict(base, observed_at=parse_ts(rec["recorded_at"]), source=f"{ef.path.name}:ledger")
                observations.extend(observe("ledger", rec, ctx))
        else:
            seen = parse_ts(doc["captured_at"])
            for rec in doc["records"]:
                ctx = dict(base, observed_at=seen, system_hint=SINGLE_COLLECTION_SYSTEM.get(doc["collection"]),
                           source=f"{ef.path.name}:{doc['collection']}")
                observations.extend(observe(doc["collection"], rec, ctx))
    return observations, coverages

