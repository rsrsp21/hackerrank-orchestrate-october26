"""Phase 8: output profile and manual spot checks of eval cases against the raw evidence.

    uv run python code/explore/spot_check.py --profile
    uv run python code/explore/spot_check.py case_34 case_46 ...

For each case: the request, the resolved subject, every step, and for every cited evidence id the observation(s)
it came from (source, record time, file capture time vs audit_at), so a reviewer can confirm the step by eye.
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from evidence.index import build  # noqa: E402
from identity import parse_ts  # noqa: E402
from investigate import investigate_all  # noqa: E402


def profile(rows, requests):
    print("status:", dict(Counter(r["deletion_status"] for r in rows)))
    steps = {r["case_id"]: json.loads(r["steps_json"]) for r in rows}
    print("steps per case:", dict(sorted(Counter(len(s) for s in steps.values()).items())))
    print("operations:", dict(Counter(f"{s['phase'][:4]}:{s['operation']}" for v in steps.values() for s in v).most_common()))
    cited = Counter(s["evidence_id"] for v in steps.values() for s in v if s["evidence_id"])
    print(f"distinct evidence ids cited: {len(cited)}; most cited: {cited.most_common(8)}")
    langs = Counter("non-ASCII" if any(ord(ch) > 127 for ch in r["request_text"]) else "ASCII" for r in requests.values())
    print("request text script:", dict(langs))


def show(case_id, inv, req, index):
    audit, since = parse_ts(req["audit_at"]), parse_ts(req["requested_at"])
    print("\n" + "=" * 100)
    print(f"{case_id} | {inv.status} | reported {req['reported_status']} | requested {req['requested_at']} | audit {req['audit_at']}")
    print(f"  text: {req['request_text'][:140]}")
    if inv.subject:
        s = inv.subject
        print(f"  subject {s.user_id} ({s.match}{' via ' + s.match_audit_id if s.match_audit_id else ''}); emails {sorted(s.emails)}")
        print(f"  account {inv.account.resource_id} [{inv.account.link}] state={inv.account.state} ev={inv.account.evidence_id or '-'}")
    for r in inv.resources:
        print(f"  resource {r.system_id}/{r.resource_id} cat={r.category.value if r.category else None} state={r.state.value if r.state else None} "
              f"action={r.action} ev={r.evidence_id or '-'} link={r.link}")
    for note in inv.notes:
        print(f"  note: {note}")
    from policy import steps_for
    for st in steps_for(inv):
        print(f"   {st['step_no']:2d} {st['phase'][:5]} {st['operation']:26s} {st['system_id']}/{st['resource_id']} ev={st['evidence_id'] or '-'}")
        if st["evidence_id"]:
            obs = [o for o in index.by_rid.get(st["resource_id"], []) if o.evidence_id == st["evidence_id"]]
            om = index.omission(st["resource_id"], audit, since)
            for o in obs[-2:]:
                print(f"        ↳ {o.source} | record {o.observed_at.isoformat()} | file {o.file_captured_at.isoformat()} | {o.state.value}")
            if not obs and om is not None and om.evidence_id == st["evidence_id"]:
                print(f"        ↳ OMISSION: absent from {om.source} (snapshot {om.observed_at.isoformat()})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="*")
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    with open(ROOT / "output.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with open(ROOT / "dataset" / "deletion_requests.csv", newline="", encoding="utf-8") as f:
        requests = {r["case_id"]: r for r in csv.DictReader(f)}
    if args.profile:
        profile(rows, requests)
    if args.cases:
        index = build(ROOT / "dataset")
        cases = investigate_all(ROOT / "dataset", index=index)
        for cid in args.cases:
            show(cid, cases[cid], requests[cid], index)


if __name__ == "__main__":
    main()
