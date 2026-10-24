"""Phase 1 task 1.2: profile the structured CSV inputs in dataset/.

Read-only exploration. Prints a report to stdout; nothing here is used for predictions.
Run: uv run python code/explore/profile_csv.py
"""

import csv
import hashlib
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "dataset"


def read(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def section(title):
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


def prefix(resource_id):
    return re.sub(r"_?\d+$", "", resource_id) or resource_id


requests = read("deletion_requests.csv")
samples = read("sample_deletion_requests.csv")
identities = read("user_identities.csv")
audit = read("user_audit_log.csv")
activity = read("system_activity.csv")
evidence = read("evidence_files.csv")

# ---------------------------------------------------------------- timestamps
section("Timestamp parsing and ranges")
for name, rows, cols in [
    ("deletion_requests", requests, ["requested_at", "reported_at", "audit_at"]),
    ("sample_requests", samples, ["requested_at", "reported_at", "audit_at"]),
    ("user_identities", identities, ["updated_at"]),
    ("user_audit_log", audit, ["event_time"]),
    ("system_activity", activity, ["event_time"]),
    ("evidence_files", evidence, ["captured_at"]),
]:
    for col in cols:
        values = sorted(ts(r[col]) for r in rows)
        print(f"{name}.{col}: {values[0].isoformat()} .. {values[-1].isoformat()} (n={len(values)})")

bad_order = [
    r["case_id"]
    for r in requests + samples
    if not (ts(r["requested_at"]) <= ts(r["reported_at"]) <= ts(r["audit_at"]))
]
print(f"requests where NOT requested_at <= reported_at <= audit_at: {bad_order or 'none'}")
print("reported_status (eval):", dict(Counter(r["reported_status"] for r in requests)))
print("reported_status (sample):", dict(Counter(r["reported_status"] for r in samples)))

# ---------------------------------------------------------------- activity
section("system_activity: event_type x source -> target")
pivot = Counter((r["event_type"], r["source_system"], r["target_system"]) for r in activity)
for (event, src, tgt), n in sorted(pivot.items()):
    print(f"{n:5d}  {event:24s} {src:22s} -> {tgt}")

section("system_activity: event_type x reported_result")
for event in sorted({r["event_type"] for r in activity}):
    results = Counter(r["reported_result"] for r in activity if r["event_type"] == event)
    print(f"{event:24s} {dict(results)}")

section("system_activity: resource_id prefixes per target_system")
prefixes = defaultdict(Counter)
for r in activity:
    prefixes[r["target_system"]][prefix(r["resource_id"])] += 1
for tgt in sorted(prefixes):
    print(f"{tgt:30s} {dict(prefixes[tgt])}")

section("system_activity: distinct details templates per event_type (digits/ids masked)")
templates = defaultdict(Counter)
examples = {}
for r in activity:
    t = re.sub(r"[\w.+-]+@[\w.-]+", "<EMAIL>", r["details"])
    t = re.sub(r"\b[0-9a-f]{64}\b", "<HASH>", t)
    t = re.sub(r"\b[a-z_]+_\d+\b", "<ID>", t)
    t = re.sub(r"\d", "#", t)
    templates[r["event_type"]][t] += 1
    examples.setdefault((r["event_type"], t), r)
for event in sorted(templates):
    print(f"\n-- {event} ({len(templates[event])} templates)")
    for t, n in templates[event].most_common(8):
        ex = examples[(event, t)]
        print(f"  {n:4d}  {t}")
        print(f"        e.g. {ex['activity_id']} {ex['resource_id']}: {ex['details'][:160]}")

section("Identifiers appearing inside activity details")
email_in_details = sum(bool(re.search(r"@", r["details"])) for r in activity)
user_in_details = sum(bool(re.search(r"\buser_\d+\b", r["details"])) for r in activity)
hash_in_details = sum(bool(re.search(r"\b[0-9a-f]{64}\b", r["details"])) for r in activity)
print(f"rows with an email: {email_in_details}; with user_id: {user_in_details}; with 64-hex hash: {hash_in_details}")

section("LINK_RESOURCE_IDENTITY and CLASSIFY_REQUEST and RESTORE_BACKUP (all rows)")
for r in activity:
    if r["event_type"] in {"LINK_RESOURCE_IDENTITY", "CLASSIFY_REQUEST", "RESTORE_BACKUP"}:
        print(f"{r['activity_id']} {r['event_time']} {r['event_type']} {r['source_system']}->{r['target_system']} "
              f"{r['resource_id']} {r['reported_result']} | {r['details']}")

# ---------------------------------------------------------------- identities
section("email_hash algorithm check")
checks = {
    "sha256(email)": lambda e: hashlib.sha256(e.encode()).hexdigest(),
    "sha256(lower(strip(email)))": lambda e: hashlib.sha256(e.strip().lower().encode()).hexdigest(),
    "md5(email)": lambda e: hashlib.md5(e.encode()).hexdigest(),
}
for label, fn in checks.items():
    ok = sum(fn(r["email"]) == r["email_hash"] for r in identities)
    print(f"{label:30s} matches {ok}/{len(identities)}")

section("user_audit_log structure")
print("field_name:", dict(Counter(r["field_name"] for r in audit)))
per_user = Counter(r["user_id"] for r in audit)
print("users with history:", len(per_user), "| max changes per user:", max(per_user.values()))
known_users = {r["user_id"] for r in identities}
print("audit users missing from identities:", len(set(per_user) - known_users))
# email-change and hash-change pairing
email_changes = {(r["user_id"], r["event_time"]) for r in audit if r["field_name"] == "email"}
hash_changes = {(r["user_id"], r["event_time"]) for r in audit if r["field_name"] == "email_hash"}
print("email changes with a same-time hash change:", len(email_changes & hash_changes), "/", len(email_changes))
# does history chain into the current snapshot?
current = {r["user_id"]: r for r in identities}
last_new = {}
for r in sorted(audit, key=lambda r: r["event_time"]):
    last_new[(r["user_id"], r["field_name"])] = r["new_value"]
chain_ok = sum(current[u][f] == v for (u, f), v in last_new.items() if u in current)
print(f"latest audit new_value equals current snapshot value: {chain_ok}/{len(last_new)}")
changes_after_snapshot = sum(ts(r["event_time"]) > ts(current[r["user_id"]]["updated_at"]) for r in audit if r["user_id"] in current)
print("audit events after the user's snapshot updated_at:", changes_after_snapshot)
dupe_emails = [e for e, n in Counter(r["email"].lower() for r in identities).items() if n > 1]
dupe_names = [e for e, n in Counter(r["name"] for r in identities).items() if n > 1]
print("duplicate current emails:", len(dupe_emails), "| duplicate names:", len(dupe_names))

section("Request email resolution")
current_email = defaultdict(set)
for r in identities:
    current_email[r["email"].lower()].add(r["user_id"])
historical_email = defaultdict(list)
for r in audit:
    if r["field_name"] == "email":
        historical_email[r["old_value"].lower()].append((r["user_id"], r["event_time"]))
        historical_email[r["new_value"].lower()].append((r["user_id"], r["event_time"]))
for label, rows in [("eval", requests), ("sample", samples)]:
    kinds = Counter()
    for r in rows:
        e = r["email"].strip().lower()
        cur, hist = current_email.get(e, set()), {u for u, _ in historical_email.get(e, [])}
        if cur and hist and cur != hist:
            kinds["ambiguous: current and historical differ"] += 1
        elif cur and len(cur) > 1:
            kinds["ambiguous: several current users"] += 1
        elif cur:
            kinds["current"] += 1
        elif hist:
            kinds["historical only"] += 1
        else:
            kinds["unresolved"] += 1
    print(f"{label}: {dict(kinds)}")
emails = Counter(r["email"].lower() for r in requests)
print("eval emails used by more than one case:", sum(n > 1 for n in emails.values()))

section("Request text overview")
lengths = [len(r["request_text"]) for r in requests]
print(f"length chars min/median/max: {min(lengths)}/{sorted(lengths)[len(lengths)//2]}/{max(lengths)}")
non_ascii = sum(any(ord(c) > 127 for c in r["request_text"]) for r in requests)
print("eval texts containing non-ASCII characters:", non_ascii)
first_sentences = Counter(re.split(r"(?<=[.!?。])\s*", r["request_text"])[0] for r in requests)
print("distinct first sentences:", len(first_sentences))
for s, n in first_sentences.most_common(60):
    print(f"  {n:4d}  {s[:150]}")

section("evidence_files manifest")
print("origins:", dict(Counter(r["origin"] for r in evidence)))
missing = [r["file_path"] for r in evidence if not (DATA / r["file_path"]).exists()]
print("manifest paths missing on disk:", missing or "none")
on_disk = {p.relative_to(DATA).as_posix() for p in (DATA / "evidence").rglob("*") if p.is_file()}
print("files on disk not in manifest:", sorted(on_disk - {r["file_path"] for r in evidence}) or "none")
audits = sorted(ts(r["audit_at"]) for r in requests)
late = [r["file_id"] for r in evidence if ts(r["captured_at"]) > audits[-1]]
print("evidence captured after every eval audit_at:", late or "none")
