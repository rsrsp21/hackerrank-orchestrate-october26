"""Phase 4 task 4.6: run the joint workflow assignment over all deletion requests and measure it on the samples.

Run: uv run python code/explore/workflow_report.py
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from evidence.index import build  # noqa: E402
from identity import IdentityResolver, load_identity_tables, parse_ts  # noqa: E402
from intent import DELETION, classify  # noqa: E402
from linking import identifier_links  # noqa: E402
from workflow import WorkflowRequest, assign_workflows  # noqa: E402


def load_requests():
    rows = []
    for name in ("deletion_requests.csv", "sample_deletion_requests.csv"):
        rows += list(csv.DictReader(open(ROOT / "dataset" / name, encoding="utf-8")))
    return rows


def main():
    idx = build(ROOT / "dataset")
    resolver = IdentityResolver(*load_identity_tables(ROOT / "dataset"))
    requests, owners = [], {}
    for r in load_requests():
        if classify(r["request_text"]).label != DELETION:
            continue
        s = resolver.resolve(r["email"], parse_ts(r["audit_at"]))
        requests.append(WorkflowRequest(r["case_id"], s.user_id, parse_ts(r["requested_at"]), parse_ts(r["reported_at"]),
                                        parse_ts(r["audit_at"]), r["reported_status"]))
        for rid in identifier_links(s, idx, None):
            owners.setdefault(rid, set()).add(s.user_id)
    links = assign_workflows(requests, idx.activities, owners,
                             lambda req, rid: bool(idx.usable(rid, req.audit_at, req.requested_at)))

    methods = Counter((k, (v.method if v else "none")) for wl in links.values() for k, v in wl.items())
    print(f"deletion requests: {len(requests)}")
    for k, n in sorted(methods.items()):
        print(f"  {k[0]:9s} {k[1]:15s} {n}")
    user_of = {r.case_id: r.user_id for r in requests}
    holders = {}
    for cid, wl in links.items():
        holders.setdefault(wl["account"].resource_id, set()).add(user_of[cid])
    print("accounts shared by different subjects:", {a: sorted(u) for a, u in holders.items() if len(u) > 1} or "none")

    expected = {r["case_id"]: json.loads(r["steps_json"]) for r in csv.DictReader(open(ROOT / "dataset" / "sample_output.csv", encoding="utf-8"))}
    acc_ok = ana_ok = ana_n = 0
    for cid, steps in sorted(expected.items(), key=lambda kv: int(kv[0][5:])):
        exp_acc = next(s["resource_id"] for s in steps if s["system_id"] == "account_service" and s["operation"] == "VERIFY_RECORD_ABSENT")
        exp_ana = {s["resource_id"] for s in steps if s["system_id"] == "analytics_platform"}
        got = links[cid]
        a = got["account"].resource_id if got["account"] else None
        acc_ok += a == exp_acc
        if exp_ana:
            ana_n += 1
            ana_ok += bool(got["analytics"]) and got["analytics"].resource_id in exp_ana
        flag = "" if a == exp_acc else f"  <-- expected {exp_acc}"
        ana = f"{got['analytics'].resource_id}({got['analytics'].method})" if got["analytics"] else "-"
        print(f"  {cid}: account {a}({got['account'].method if got['account'] else '-'}){flag} | analytics {ana} expected {sorted(exp_ana) or '-'}")
    print(f"sample account accuracy: {acc_ok}/{len(expected)}; analytics accuracy where expected: {ana_ok}/{ana_n}")


if __name__ == "__main__":
    main()
