"""Phase 3 task 3.4: resolve every request (eval + sample) and report the results.

Prints match counts, errors, historical matches with their proving audit_id, users with email chains,
requests sharing a subject, and identifier-set size statistics.
Run: uv run python code/explore/identity_report.py
"""

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from identity import IdentityError, IdentityResolver, load_identity_tables, parse_ts  # noqa: E402


def main():
    identities, audit = load_identity_tables(ROOT / "dataset")
    resolver = IdentityResolver(identities, audit)
    by_user = defaultdict(list)
    for name in ("deletion_requests.csv", "sample_deletion_requests.csv"):
        rows = list(csv.DictReader(open(ROOT / "dataset" / name, encoding="utf-8")))
        counts, errors, sizes = Counter(), [], Counter()
        print(f"\n=== {name} ({len(rows)} requests)")
        for r in rows:
            try:
                s = resolver.resolve(r["email"], parse_ts(r["audit_at"]))
            except IdentityError as exc:
                errors.append((r["case_id"], str(exc)))
                continue
            counts[s.match] += 1
            sizes[(len(s.emails), len(s.email_hashes), len(s.phones))] += 1
            by_user[s.user_id].append((r["case_id"], r["email"], s.match, s.match_audit_id, r["audit_at"]))
            if s.match == "historical" and "sample" in name:
                print(f"  historical: {r['case_id']} -> {s.user_id} via {s.match_audit_id}")
        print(f"  matches: {dict(counts)}  errors: {len(errors)}")
        for e in errors:
            print("  ERROR", e)
        print(f"  identifier-set sizes (emails, hashes, phones): {dict(sorted(sizes.items()))}")

    print("\n=== requests sharing a subject")
    for user_id, reqs in sorted(by_user.items()):
        if len(reqs) > 1:
            print(f"  {user_id}: {reqs}")

    print("\n=== task 3.5: sample subjects vs plan/sample_walkthrough.md §3")
    table = (ROOT / "plan" / "sample_walkthrough.md").read_text(encoding="utf-8")
    expected = {f"case_{m.group(1)}": (m.group(2), m.group(3)) for m in
                re.finditer(r"^\| (\d\d) \| (user_\d+) \(\**(current|historical)", table, re.M)}
    got = {c: (u, match) for u, reqs in by_user.items() for c, _, match, _, _ in reqs if c in expected}
    bad = {c: (expected[c], got.get(c)) for c in expected if got.get(c) != expected[c]}
    print(f"  walkthrough rows: {len(expected)}; matching: {len(expected) - len(bad)}; mismatches: {bad or 'none'}")

    print("\n=== users with more than one email change")
    chains = Counter(a["user_id"] for a in audit if a["field_name"] == "email")
    for user_id, n in chains.items():
        if n > 1:
            print(f"  {user_id}: {n} changes; requests: {[c for c, *_ in by_user.get(user_id, [])]}")


if __name__ == "__main__":
    main()
