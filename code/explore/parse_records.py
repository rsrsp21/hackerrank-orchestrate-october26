"""Phase 1 task 1.4 (records): flatten every JSON/TXT record file into uniform observations.

Families (see plan/data_notes.md §3):
  customer_data_snapshot_bundle_*   {exported_at, snapshots[{captured_at, data_store, collection, records[]}]}
  service_resource_export_*         {exported_at, region, service_exports{system{collection[]: {observed_at, ...}}}}
  ledger (connector_configurations, customer_export_manifest, security_audit_ledger)
                                    {exported_at, origin, records[{recorded_at, system, resource_id, record_type, result, subject_reference}]}
  single collection (customer_analytics_report, customer_export_jobs)
                                    {captured_at, source, collection, records[]}
  customer_account_handover_*.txt   "- ts | system | resource_id | record_type | result | identifier"
Observation: file_id, file, file_captured_at, observed_at, system, collection, resource_id, record_type, result, fields
Run: uv run python code/explore/parse_records.py
"""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"


def obs(m, path, observed_at, system, collection, record, record_type=None, result=None):
    return dict(file_id=m["file_id"], file=path.name, file_captured_at=m["captured_at"], observed_at=observed_at,
                system=system, collection=collection, resource_id=record.get("resource_id"),
                record_type=record_type or record.get("record_type"), result=result or record.get("result"),
                fields=record)


def parse(path, m):
    if path.suffix == ".txt":
        out = []
        snap = re.search(r"Snapshot: (\S+)", path.read_text(encoding="utf-8"))
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = [p.strip() for p in line.lstrip("- ").split("|")]
            if line.startswith("- ") and len(parts) == 6:
                ts, system, rid, rtype, result, ident = parts
                rec = {"resource_id": rid, "subject_reference": None if ident == "no direct identifier" else ident}
                out.append(obs(m, path, ts, system, "handover_check", rec, rtype, result))
        return out, {"snapshot": snap and snap.group(1)}
    d = json.loads(path.read_text(encoding="utf-8"))
    out = []
    if "snapshots" in d:
        for s in d["snapshots"]:
            for r in s["records"]:
                system = r.get("system", s["data_store"]) if "record_type" in r else s["data_store"]
                out.append(obs(m, path, r.get("recorded_at", s["captured_at"]), system, s["collection"], r))
        meta = {"exported_at": d["exported_at"],
                "empty_snapshots": [(s["captured_at"], s["data_store"], s["collection"]) for s in d["snapshots"] if not s["records"]]}
        return out, meta
    if "service_exports" in d:
        for system, colls in d["service_exports"].items():
            for coll, rows in colls.items():
                for r in rows:
                    out.append(obs(m, path, r.get("observed_at"), system, coll, r))
        return out, {"exported_at": d["exported_at"], "region": d.get("region")}
    if "record_count" in d:
        for r in d["records"]:
            out.append(obs(m, path, r["recorded_at"], r["system"], "ledger", r))
        return out, {"exported_at": d["exported_at"], "origin": d["origin"], "record_count_ok": d["record_count"] == len(d["records"])}
    for r in d["records"]:
        out.append(obs(m, path, d["captured_at"], d["source"], d["collection"], r))
    return out, {"captured_at": d["captured_at"], "source": d["source"]}


def main():
    manifest = {r["file_path"]: r for r in csv.DictReader(open(DATA / "evidence_files.csv", encoding="utf-8"))}
    allobs = []
    print("=" * 80, "\nPer-file: observation counts and time relations\n" + "=" * 80)
    for path in sorted((DATA / "evidence" / "records").iterdir()):
        m = manifest[path.relative_to(DATA).as_posix()]
        o, meta = parse(path, m)
        times = sorted(x["observed_at"] for x in o if x["observed_at"])
        after = sum(t > m["captured_at"] for t in times)
        print(f"{m['file_id']} {path.name:52s} n={len(o):3d} observed={times[0] if times else '-'}..{times[-1] if times else '-'} "
              f"captured={m['captured_at']} after_capture={after} origin={m['origin']}")
        print(f"      meta={meta}")
        allobs.extend(o)

    print("\n" + "=" * 80, "\n(system, collection) -> record count, result values\n" + "=" * 80)
    groups = defaultdict(list)
    for o in allobs:
        groups[(o["system"], o["collection"])].append(o)
    for k in sorted(groups):
        rs = groups[k]
        res = Counter((o["record_type"], o["result"]) for o in rs if o["result"] or o["record_type"])
        status = Counter(str(o["fields"].get("status_code")) for o in rs if "status_code" in o["fields"])
        print(f"{str(k):70s} n={len(rs):3d} {dict(res) if res else ''} {('status_code=' + str(dict(status))) if status else ''}")

    print("\n" + "=" * 80, "\nLedger vocabulary: record_type x result (all ledger-style sources)\n" + "=" * 80)
    voc = Counter((o["record_type"], o["system"], o["result"]) for o in allobs if o["result"])
    for k, n in sorted(voc.items()):
        print(f"   {n:4d}  {k}")
    print("\nledger identifier kinds:", Counter(
        "none" if not v else ("email" if "@" in v else ("user_id" if v.startswith("user_") else "other"))
        for o in allobs if o["result"] for v in [o["fields"].get("subject_reference") or o["fields"].get("lookup_value")]))

    print("\n" + "=" * 80, "\nSearch index queries (service_resource_export)\n" + "=" * 80)
    q = [o for o in allobs if o["collection"] == "index_queries"]
    print("hits.total distribution:", Counter(o["fields"]["hits"]["total"] for o in q))
    print("query == hit email:", Counter(
        all(d.get("email", "").lower() == o["fields"]["query"].lower() for d in o["fields"]["hits"]["documents"]) for o in q))
    print("query resource_id == hit resource_id:", Counter(
        all(d["resource_id"] == o["resource_id"] for d in o["fields"]["hits"]["documents"]) for o in q))

    print("\n" + "=" * 80, "\nResources observed more than once across record files (timeline material)\n" + "=" * 80)
    seen = defaultdict(list)
    for o in allobs:
        if o["resource_id"]:
            seen[o["resource_id"]].append(o)
    multi = {r: v for r, v in seen.items() if len({x["file_id"] for x in v}) > 1}
    print(f"{len(multi)} resources appear in more than one record file (of {len(seen)})")
    for r in sorted(multi)[:12]:
        print(f"  {r}: " + " | ".join(f"{x['file_id']}@{x['observed_at']} {x['collection']} {x['result'] or ''}" for x in sorted(multi[r], key=lambda x: x["observed_at"] or "")))

    out = ROOT / "code" / "cache" / "extracted"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "record_observations.jsonl", "w", encoding="utf-8") as f:
        for o in allobs:
            f.write(json.dumps(o, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(allobs)} observations to {out / 'record_observations.jsonl'}")


if __name__ == "__main__":
    main()
