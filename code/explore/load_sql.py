"""Phase 1 task 1.3: profile the SQL snapshot evidence.

Each .sql file is executed into its own in-memory SQLite database (source files are never modified).
Rows from every table are flattened into one observation shape so the families can be compared:
    file_id, file_name, captured_at, topology, table, role, resource_id, origin_system, collection,
    fields (dict of every column / record_json key), updated_at
Run: uv run python code/explore/load_sql.py
"""

import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"

IDENTITY_KEYS = {
    "email": ["email", "requester_email", "owner_email", "customer_email"],
    "phone": ["phone", "requester_phone", "owner_phone"],
    "name": ["full_name", "display_name", "requester_name"],
    "email_hash": ["email_hash"],
    "user_id": ["user_id", "customer_reference", "subject_reference"],
}


def manifest():
    with open(DATA / "evidence_files.csv", newline="", encoding="utf-8") as f:
        return {r["file_path"]: r for r in csv.DictReader(f)}


def header_meta(text):
    meta = {}
    for key in ("Captured at", "Database topology"):
        m = re.search(rf"^-- {key}: (.+)$", text, re.M)
        if m:
            meta[key] = m.group(1).strip()
    return meta


def role_of(table):
    """primary / replica name derived from the table name."""
    if table == "snapshot_scope":
        return "scope"
    if "primary" in table:
        return "primary"
    for marker in ("read_replica", "reporting_replica", "failover_replica"):
        if marker in table:
            return marker
    m = re.search(r"replica_(\w+)$", table)
    if m:
        return f"regional_replica_{m.group(1)}"
    return "inventory"


def load(path):
    text = path.read_text(encoding="utf-8")
    con = sqlite3.connect(":memory:")
    con.executescript(text)
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    rows = {t: [dict(r) for r in con.execute(f'SELECT * FROM "{t}"')] for t in tables}
    columns = {t: [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')] for t in tables}
    return header_meta(text), tables, columns, rows


def flatten(row):
    fields = dict(row)
    if "record_json" in fields:
        fields.update(json.loads(fields.pop("record_json")))
    return fields


def identity_view(fields):
    out = {}
    for kind, keys in IDENTITY_KEYS.items():
        for k in keys:
            if fields.get(k) not in (None, ""):
                out.setdefault(kind, []).append((k, fields[k]))
    return out


def main():
    files = manifest()
    identities = list(csv.DictReader(open(DATA / "user_identities.csv", encoding="utf-8")))
    audit = list(csv.DictReader(open(DATA / "user_audit_log.csv", encoding="utf-8")))
    by_email, by_hash, by_phone, user_ids = {}, {}, {}, set()
    for r in identities:
        user_ids.add(r["user_id"])
        by_email[r["email"].lower()] = r["user_id"]
        by_hash[r["email_hash"]] = r["user_id"]
        by_phone[re.sub(r"\D", "", r["phone"])] = r["user_id"]
    for r in audit:
        for v in (r["old_value"], r["new_value"]):
            if r["field_name"] == "email":
                by_email.setdefault(v.lower(), r["user_id"])
            elif r["field_name"] == "email_hash":
                by_hash.setdefault(v, r["user_id"])
            elif r["field_name"] == "phone":
                by_phone.setdefault(re.sub(r"\D", "", v), r["user_id"])

    observations = []
    print("=" * 80, "\nPer-file structure\n" + "=" * 80)
    for path in sorted((DATA / "evidence" / "databases").glob("*.sql")):
        rel = path.relative_to(DATA).as_posix()
        meta, tables, columns, rows = load(path)
        m = files[rel]
        print(f"\n{m['file_id']}  {path.name}  manifest_captured={m['captured_at']}  origin={m['origin']}")
        print(f"   header: {meta}")
        for t in tables:
            print(f"   {t:38s} rows={len(rows[t]):3d} role={role_of(t):26s} cols={columns[t]}")
        for t in tables:
            if t == "snapshot_scope":
                continue
            for r in rows[t]:
                f = flatten(r)
                observations.append({
                    "file_id": m["file_id"], "file": path.name, "captured_at": m["captured_at"],
                    "topology": meta.get("Database topology", "inventory"), "table": t, "role": role_of(t),
                    "resource_id": f.get("resource_id"), "origin_system": f.get("origin_system"),
                    "collection": f.get("collection_name", t), "fields": f,
                })

    print("\n" + "=" * 80, "\nCollections, origin systems, and field keys\n" + "=" * 80)
    keys = defaultdict(Counter)
    origins = defaultdict(Counter)
    for o in observations:
        keys[o["collection"]].update(k for k in o["fields"] if k not in ("resource_id", "origin_system", "collection_name"))
        origins[o["collection"]][o["origin_system"] or "-"] += 1
    for c in sorted(keys):
        print(f"\n{c}: origins={dict(origins[c])}")
        print(f"   keys={dict(keys[c])}")

    print("\n" + "=" * 80, "\nValue representations (status-like and identity fields)\n" + "=" * 80)
    status_keys = ["account_status", "enabled", "restore_allowed", "last_delivery_status", "index_name",
                   "audience_cohort", "event_name", "event_code", "status", "state", "connector_name",
                   "retention_until", "legal_hold", "attachment_scope"]
    for c in sorted(keys):
        for k in status_keys:
            vals = Counter(str(o["fields"].get(k)) for o in observations if o["collection"] == c and k in o["fields"])
            if vals:
                print(f"{c}.{k}: {dict(vals.most_common(12))}")
    redaction_like = Counter()
    for o in observations:
        for k, v in o["fields"].items():
            if isinstance(v, str) and re.search(r"redact|\*\*\*|anonym|removed|deleted|tombstone", v, re.I):
                redaction_like[(o["collection"], k, v[:60])] += 1
    print("\nredaction-like literal values:")
    for (c, k, v), n in redaction_like.most_common(30):
        print(f"   {n:4d}  {c}.{k} = {v!r}")
    case_variants = sum(
        1 for o in observations for _, v in identity_view(o["fields"]).get("email", []) if v != v.lower()
    )
    print(f"\nemail values not lowercase: {case_variants}")

    print("\n" + "=" * 80, "\nLinking rows to known users\n" + "=" * 80)
    link_kinds = Counter()
    unlinked_with_ids = Counter()
    unknown_user_refs = Counter()
    for o in observations:
        view = identity_view(o["fields"])
        hits = set()
        for _, v in view.get("email", []):
            if v.lower() in by_email:
                hits.add(("email", by_email[v.lower()]))
        for _, v in view.get("email_hash", []):
            if v in by_hash:
                hits.add(("hash", by_hash[v]))
        for _, v in view.get("phone", []):
            if re.sub(r"\D", "", v) in by_phone:
                hits.add(("phone", by_phone[re.sub(r"\D", "", v)]))
        for k, v in view.get("user_id", []):
            if v in user_ids:
                hits.add((k, v))
            else:
                unknown_user_refs[(o["collection"], k)] += 1
        users = {u for _, u in hits}
        if len(users) > 1:
            link_kinds["CONFLICT (several users)"] += 1
        link_kinds[" + ".join(sorted({k for k, _ in hits})) or ("no identity fields" if not view else "identity fields but unknown")] += 1
        if view and not hits:
            unlinked_with_ids[o["collection"]] += 1
    for k, n in link_kinds.most_common():
        print(f"   {n:4d}  {k}")
    print("rows carrying identifiers that match no known user, per collection:", dict(unlinked_with_ids))
    print("user refs not in user_identities (decoy/external ids):", dict(unknown_user_refs))

    print("\n" + "=" * 80, "\nReplication drift (same file: primary vs replica tables)\n" + "=" * 80)
    by_file = defaultdict(lambda: defaultdict(dict))
    for o in observations:
        by_file[o["file"]][o["role"]][o["resource_id"]] = o["fields"]
    drift_examples = 0
    for fname in sorted(by_file):
        roles = by_file[fname]
        if "primary" not in roles or len(roles) < 2:
            continue
        prim = roles["primary"]
        for role, rep in roles.items():
            if role == "primary":
                continue
            only_rep = sorted(set(rep) - set(prim))
            only_prim = sorted(set(prim) - set(rep))
            changed = sorted(r for r in set(rep) & set(prim) if strip_ts(rep[r]) != strip_ts(prim[r]))
            print(f"{fname} [{role}] only_in_replica={only_rep} only_in_primary={only_prim} differing={changed}")
            for r in (only_rep + changed)[:3]:
                if drift_examples < 12:
                    drift_examples += 1
                    print(f"      {r}: primary={summ(prim.get(r))}")
                    print(f"      {' ' * len(r)}  replica={summ(rep.get(r))}")

    print("\n" + "=" * 80, "\nInventory snapshots: resource state across time\n" + "=" * 80)
    timeline = defaultdict(list)
    for o in observations:
        timeline[(o["collection"], o["resource_id"])].append((o["captured_at"], o["file_id"], o["role"], o["fields"]))
    multi = {k: v for k, v in timeline.items() if len({x[0] for x in v}) > 1}
    print(f"resources seen in more than one snapshot: {len(multi)} of {len(timeline)}")
    for (c, r), seen in list(sorted(multi.items()))[:8]:
        print(f"  {c}/{r}")
        for cap, fid, role, f in sorted(seen, key=lambda x: x[0]):
            print(f"     {cap} {fid} {role}: {summ(f)}")

    low_ids = sorted({o["resource_id"] for o in observations if re.search(r"_0\d\d$|_\d{1,2}$", o["resource_id"] or "")})
    print("\nlow-numbered (scenario-style) resource ids in SQL:", low_ids)

    out = ROOT / "code" / "cache" / "extracted"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "sql_observations.jsonl", "w", encoding="utf-8") as f:
        for o in observations:
            f.write(json.dumps(o, sort_keys=True, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(observations)} observations to {out / 'sql_observations.jsonl'}")


def strip_ts(fields):
    return {k: v for k, v in fields.items() if k not in ("updated_at",)}


def summ(fields):
    if fields is None:
        return "<absent>"
    keep = {k: v for k, v in fields.items() if k not in ("metrics", "recent_activity", "integrity_seal", "origin_system", "collection_name", "resource_id")}
    for k in ("email_hash",):
        if keep.get(k):
            keep[k] = keep[k][:10] + "…"
    return json.dumps(keep, ensure_ascii=False)[:260]


if __name__ == "__main__":
    main()
