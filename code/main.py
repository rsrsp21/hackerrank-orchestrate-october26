"""Ghost Data Still Exists — deletion-audit agent entry point.

    uv run python code/main.py [--data dataset] [--out output.csv]

Reads every participant file under dataset/, investigates each request in deletion_requests.csv, and writes
output.csv (case_id, deletion_status, steps_json) sorted numerically by case_id. Sample requests are
investigated alongside the evaluation requests because concurrent deletion workflows are assigned jointly;
their answers are never read. The previous output.csv is kept as code/cache/output_prev.csv.
"""

import argparse
import csv
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from investigate import investigate_all, load_requests  # noqa: E402
from policy import serialize, steps_for  # noqa: E402


def case_number(case_id):
    digits = "".join(ch for ch in case_id if ch.isdigit())
    return (int(digits) if digits else 0, case_id)


def run(data_dir, out_path):
    started = time.perf_counter()
    eval_requests = load_requests(data_dir, ("deletion_requests.csv",))
    all_requests = load_requests(data_dir)  # eval + sample requests (inputs only)
    cases = investigate_all(data_dir, all_requests)
    rows = []
    for r in sorted(eval_requests, key=lambda r: case_number(r["case_id"])):
        inv = cases[r["case_id"]]
        rows.append((r["case_id"], inv.status, serialize(steps_for(inv))))
    out_path = Path(out_path)
    if out_path.exists():
        backup = ROOT / "code" / "cache" / "output_prev.csv"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out_path, backup)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["case_id", "deletion_status", "steps_json"])
        writer.writerows(rows)
    status = Counter(s for _, s, _ in rows)
    print(f"wrote {len(rows)} rows to {out_path} in {time.perf_counter() - started:.1f}s; status {dict(sorted(status.items()))}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", default=str(ROOT / "dataset"), help="dataset directory")
    parser.add_argument("--out", default=str(ROOT / "output.csv"), help="output CSV path")
    args = parser.parse_args()
    run(Path(args.data), Path(args.out))


if __name__ == "__main__":
    main()
