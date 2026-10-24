"""Phase 4 task 4.9: investigation quality on the samples and a health report over the eval set.

Run: uv run python code/explore/investigation_report.py
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from investigate import investigate_all  # noqa: E402

IMAGE_FILES = {"evidence_04", "evidence_09", "evidence_14", "evidence_19", "evidence_23", "evidence_28",
               "evidence_32", "evidence_37", "evidence_42", "evidence_46", "evidence_60"}


def main():
    cases = investigate_all(ROOT / "dataset")
    with open(ROOT / "dataset" / "sample_output.csv", newline="", encoding="utf-8") as f:
        expected = {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(f)}

    print("=== samples")
    tp = fn = fp = st_ok = ev_ok = ev_n = 0
    for cid, (status, steps) in sorted(expected.items(), key=lambda kv: int(kv[0][5:])):
        inv = cases[cid]
        want = {s["resource_id"] for s in steps}
        got = {inv.account.resource_id} | {x.resource_id for x in inv.resources}
        tp, fn, fp = tp + len(want & got), fn + len(want - got), fp + len(got - want)
        st_ok += inv.status == status
        cited = {inv.account.resource_id: inv.account.evidence_id} | {x.resource_id: x.evidence_id for x in inv.resources}
        for s in steps:
            if s["evidence_id"]:
                ev_n += 1
                ev_ok += cited.get(s["resource_id"]) == s["evidence_id"]
        if want != got or inv.status != status:
            print(f"  {cid}: status {inv.status} vs {status}; missing {sorted(want - got)}; extra {sorted(got - want)}")
    print(f"  status {st_ok}/{len(expected)} | resource recall {tp / (tp + fn):.3f} precision {tp / (tp + fp):.3f} "
          f"| cited evidence {ev_ok}/{ev_n}")

    ev = {c: i for c, i in cases.items() if not c.startswith("case_") or int(c[5:]) > 32}
    print(f"\n=== eval set ({len(ev)} cases)")
    print("  status:", dict(Counter(i.status for i in ev.values())))
    dels = [i for i in ev.values() if i.status != "NOT_APPLICABLE"]
    print("  account link:", dict(Counter(i.account.link.split(":")[0] + ":" + i.account.link.split(":")[1] for i in dels)))
    print("  account action:", dict(Counter(i.account.action for i in dels)))
    no_ev = [i.case_id for i in dels if i.status == "COMPLETE" and not i.account.evidence_id]
    print(f"  COMPLETE cases whose account has no citable evidence: {len(no_ev)} {no_ev[:15]}")
    print("  resource (category, action):")
    for (cat, act), n in sorted(Counter((x.category.value if x.category else None, x.action)
                                        for i in dels for x in i.resources).items(), key=str):
        print(f"     {n:4d}  {cat:20s} {act}")
    print("  findings per case:", dict(sorted(Counter(len(i.findings) for i in dels).items())))
    retained = Counter(sum(x.action == "RETAIN" and x.category.value == "SECURITY_AUDIT_LOG" for x in i.resources) for i in dels)
    print("  retained audit records per case:", dict(sorted(retained.items())))
    print("  legal holds:", [(i.case_id, x.resource_id, x.evidence_id or "-") for i in dels for x in i.resources
                             if x.category and x.category.value == "LEGAL_HOLD_RECORD"])
    print("  notes:", [(i.case_id, n) for i in dels for n in i.notes])
    img = [i.case_id for i in dels if any(x.evidence_id in IMAGE_FILES for x in [i.account] + i.resources)]
    print("  cases citing image evidence:", img or "none (image facts not yet extracted)")
    low = [(i.case_id, i.account.link) for i in dels if i.account.link.startswith("L6") or "tie-break" in i.account.link]
    print(f"  low-confidence accounts (L6 or tie-break): {len(low)}")


if __name__ == "__main__":
    main()
