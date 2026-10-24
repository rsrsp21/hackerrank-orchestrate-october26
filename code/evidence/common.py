"""Manifest access shared by the evidence loaders."""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from identity import parse_ts


@dataclass(frozen=True)
class EvidenceFile:
    file_id: str
    path: Path
    origin: str
    captured_at: datetime


def load_manifest(data_dir):
    data_dir = Path(data_dir)
    with open(data_dir / "evidence_files.csv", newline="", encoding="utf-8") as f:
        return [EvidenceFile(r["file_id"], data_dir / r["file_path"], r["origin"], parse_ts(r["captured_at"]))
                for r in csv.DictReader(f)]


def files_under(manifest, folder, suffixes):
    return sorted((m for m in manifest if m.path.parent.name == folder and m.path.suffix in suffixes),
                  key=lambda m: m.file_id)
