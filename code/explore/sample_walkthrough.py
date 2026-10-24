"""Phase 1 task 1.6: explain every sample answer from the evidence.

For each sample case: resolve the subject, gather every observation that carries one of the subject's
identifiers (SQL rows, record rows, log traces/events, activity rows), expand to all observations of the
resources found, print a timeline relative to audit_at, and check each expected step against it.
Requires the caches written by load_sql.py, parse_records.py, parse_logs.py.
Run: uv run python code/explore/sample_walkthrough.py [case_id ...]
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"
CACHE = ROOT / "code" / "cache" / "extracted"

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
HASH = re.compile(r"\b[0-9a-f]{64}\b")
USER = re.compile(r"\buser_\d+\b")
RID = re.compile(r"\b(?:account|search|support|analytics|export|data_flow|backup|audit_record|legal_hold|tombstone|cache|email_delivery|marketing|object)_\d+\b")


def jl(name):
    return [json.loads(line) for line in open(CACHE / name, encoding="utf-8")]


def tokens(obj):
    text = json.dumps(obj, ensure_ascii=False)
    toks = {("email", e.lower()) for e in EMAIL.findall(text)}
    toks |= {("hash", h) for h in HASH.findall(text)}
    toks |= {("user", u) for u in USER.findall(text)}
    for k, v in (obj.items() if isinstance(obj, dict) else []):
        if isinstance(v, str) and "phone" in k:
            toks.add(("phone", re.sub(r"\D", "", v)))
    return toks


def build_observations(manifest):
    obs = []
    for o in jl("sql_observations.jsonl"):
        obs.append(dict(src="sql", eid=o["file_id"], cap=o["captured_at"], t=o["captured_at"],
                        system=o["origin_system"] or o["table"], rid=o["resource_id"],
                        what=f"{o['table']}[{o['role']}]", fields=o["fields"]))
    for o in jl("record_observations.jsonl"):
        obs.append(dict(src="rec", eid=o["file_id"], cap=o["file_captured_at"], t=o["observed_at"],
                        system=o["system"], rid=o["resource_id"],
                        what=f"{o['collection']} {o['record_type'] or ''} {o['result'] or ''}".strip(), fields=o["fields"]))
    for o in jl("log_traces.jsonl"):
        obs.append(dict(src="log", eid=o["file_id"], cap=manifest[o["file_id"]], t=o["ts"], system=o["service"],
                        rid=o["resource_id"], what=">".join(o["events"]), fields=o["fields"]))
    for o in jl("log_events.jsonl"):  # single-line events whose trace has no resource join
        f = o["fields"]
        if "resource_id" in f and o["event"] in ("message_pii_scan", "attachment_pii_scan", "analytics_identity_scan",
                                                 "analytics_profile_read", "connector_heartbeat", "connector_config_loaded",
                                                 "restore_candidate_evaluated", "message_read", "deletion_marker_check",
                                                 "retained_order_loaded", "thumbnail_failed"):
            obs.append(dict(src="logev", eid=o["file_id"], cap=o["captured_at"], t=o["ts"], system=o["service"],
                            rid=f["resource_id"], what=o["event"], fields=f))
    for a in csv.DictReader(open(DATA / "system_activity.csv", encoding="utf-8")):
        rids = set(RID.findall(a["details"])) | {a["resource_id"]}
        for rid in rids:
            obs.append(dict(src="act", eid=a["activity_id"], cap=a["event_time"], t=a["event_time"],
                            system=a["target_system"], rid=rid,
                            what=f"{a['event_type']} {a['reported_result']} {a['source_system']}->{a['target_system']}",
                            fields={"details": a["details"]}))
    for o in obs:
        o["tok"] = tokens(o["fields"])
    return obs


def subject(email, audit_at, identities, audit):
    e = email.lower()
    uid = next((r["user_id"] for r in identities if r["email"].lower() == e), None)
    how = "current"
    if not uid:
        hit = [r for r in audit if r["field_name"] == "email" and e in (r["old_value"].lower(), r["new_value"].lower())]
        uid, how = (hit[0]["user_id"], f"historical via {hit[0]['audit_id']}") if hit else (None, "UNRESOLVED")
    cur = next(r for r in identities if r["user_id"] == uid)
    toks = {("user", uid), ("email", cur["email"].lower()), ("hash", cur["email_hash"]),
            ("phone", re.sub(r"\D", "", cur["phone"]))}
    for r in audit:
        if r["user_id"] != uid:
            continue
        kind = {"email": "email", "email_hash": "hash", "phone": "phone"}[r["field_name"]]
        for v in (r["old_value"], r["new_value"]):
            v = v.lower() if kind == "email" else (re.sub(r"\D", "", v) if kind == "phone" else v)
            toks.add((kind, v))
    return uid, how, cur, toks


def main():
    manifest = {r["file_id"]: r["captured_at"] for r in csv.DictReader(open(DATA / "evidence_files.csv", encoding="utf-8"))}
    identities = list(csv.DictReader(open(DATA / "user_identities.csv", encoding="utf-8")))
    audit = list(csv.DictReader(open(DATA / "user_audit_log.csv", encoding="utf-8")))
    reqs = {r["case_id"]: r for r in csv.DictReader(open(DATA / "sample_deletion_requests.csv", encoding="utf-8"))}
    expected = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"]))
                for r in csv.DictReader(open(DATA / "sample_output.csv", encoding="utf-8"))}
    obs = build_observations(manifest)
    by_rid = defaultdict(list)
    for o in obs:
        by_rid[o["rid"]].append(o)

    wanted = sys.argv[1:] or sorted(reqs, key=lambda c: int(c.split("_")[1]))
    for cid in wanted:
        r = reqs[cid]
        A = r["audit_at"]
        uid, how, cur, toks = subject(r["email"], A, identities, audit)
        direct = [o for o in obs if o["tok"] & toks]
        rids = {o["rid"] for o in direct if o["rid"]}
        linked = {id(o): o for rid in rids for o in by_rid[rid]}
        linked.update({id(o): o for o in direct})
        status, steps = expected[cid]
        print("\n" + "#" * 110)
        print(f"{cid} expected={status} reported={r['reported_status']} requested={r['requested_at']} audit_at={A}")
        print(f"  subject {uid} ({how}) name={cur['name']} | text: {r['request_text'][:110]}")
        for s in steps:
            print(f"  EXP {s['step_no']:2d} {s['phase'][:5]} {s['operation']:26s} {s['system_id']}/{s['resource_id']} ev={s['evidence_id'] or '-'}")
        print("  -- timeline (✗ = file captured or observed after audit_at; * = carries a subject identifier)")
        for o in sorted(linked.values(), key=lambda o: (o["rid"] or "", o["t"] or "")):
            late = "✗" if (o["cap"] > A or (o["t"] or "") > A) else " "
            mark = "*" if o["tok"] & toks else " "
            f = {k: v for k, v in o["fields"].items() if k not in ("metrics", "recent_activity", "integrity_seal", "instance", "pod", "region", "duration_ms", "took_ms", "shard", "latency_ms")}
            print(f"   {late}{mark} {o['rid'] or '-':18s} {o['t'] or '-':21s} {o['eid']:13s} {o['src']:5s} {o['system'] or '-':24s} {o['what'][:55]:55s} {json.dumps(f, ensure_ascii=False)[:150]}")
        cited = {(s["resource_id"], s["evidence_id"]) for s in steps if s["evidence_id"]}
        for rid, eid in sorted(cited):
            ok = any(o["rid"] == rid and o["eid"] == eid for o in linked.values())
            print(f"  CHECK cited ({rid}, {eid}): {'found in linked observations' if ok else '!! NOT FOUND'}")
        missing = {s["resource_id"] for s in steps} - rids - {o["rid"] for o in linked.values()}
        if missing:
            print(f"  CHECK resources in answer with no linked observation: {sorted(missing)}")


if __name__ == "__main__":
    main()
