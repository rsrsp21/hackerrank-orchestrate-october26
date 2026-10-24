"""SQL snapshot evidence → Observations and account Coverage.

Each file runs in its own in-memory SQLite database (sources are never modified). Rows are observed at the
file's capture time (no row is newer than its file). Topology snapshots (files with a `Database topology`
header) that hold account profiles act as account Coverage: an account missing from every table is ABSENT
by omission. Inventory snapshots are never used for omission (sample case_04 cites evidence_54, not the
empty inventory evidence_90).
"""

import json
import re
import sqlite3

from evidence.common import files_under
from evidence.interpret import PROFILE, observe
from evidence.model import Coverage, resource_prefix


def _rows(path):
    con = sqlite3.connect(":memory:")
    con.executescript(path.read_text(encoding="utf-8"))
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    data = {t: [dict(r) for r in con.execute(f'SELECT * FROM "{t}" ORDER BY rowid')] for t in tables}
    con.close()
    return data


def load(manifest):
    observations, coverages = [], []
    for ef in files_under(manifest, "databases", {".sql"}):
        text = ef.path.read_text(encoding="utf-8")
        topology = re.search(r"^-- Database topology: (\S+)", text, re.M)
        ctx = dict(evidence_id=ef.file_id, file_captured_at=ef.captured_at, observed_at=ef.captured_at)
        accounts, holds_profiles = set(), False
        for table, rows in _rows(ef.path).items():
            if table == "snapshot_scope":
                continue
            for row in rows:
                record = dict(row)
                collection = table
                if "record_json" in record:
                    collection = record.get("collection_name") or table
                    record.update(json.loads(record.pop("record_json")))
                ctx["source"] = f"{ef.path.name}:{table}"
                observations.extend(observe(collection, record, ctx))
                if collection in PROFILE:
                    holds_profiles = True
                if resource_prefix(record.get("resource_id")) == "account":
                    accounts.add(record["resource_id"])
        if topology and holds_profiles:
            coverages.append(Coverage(ef.file_id, ef.captured_at, ef.captured_at, "account_service",
                                      frozenset(accounts), "topology_table", f"{ef.path.name} ({topology.group(1)})"))
    return observations, coverages
