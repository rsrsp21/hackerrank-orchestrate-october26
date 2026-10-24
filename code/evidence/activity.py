"""system_activity.csv → workflow claims, state signals, and data-catalog links.

Activity results are claims and never set a state by themselves. Exceptions are rows that report an
observed state rather than a requested action (phase4.md §2.2):
  CHECK_DATA_FLOW ("remains enabled")          → FLOW_ACTIVE for the data flow
  CHECK_RESTORE_ACCESS ("can still be restored") → RESTORE_ALLOWED for the backup
  "… repopulated downstream resource X"         → X PRESENT (+ the source flow/backup is live)
LINK_RESOURCE_IDENTITY rows become CatalogLinks (resource ↔ email + user_id), an explicit grounded link.
"""

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from evidence.model import Category, Observation, State, link_keys_from, resource_refs_from, system_for
from identity import norm_email, parse_ts

LINK_RE = re.compile(r"linked (?P<rid>\S+) \((?P<label>[^)]*)\) to (?P<email>\S+) and (?P<user>user_\d+)")
CONFIRMED_RE = re.compile(r"confirmed (?P<rid>\S+) \((?P<label>[^)]*)\) belongs only to (?P<email>\S+) and (?P<user>user_\d+)")
REPOPULATED_RE = re.compile(r"repopulated downstream resource (?P<rid>\w+)")
CATEGORY_BY_PREFIX = {"search": Category.SEARCH_INDEX_ENTRY, "account": Category.USER_PROFILE,
                      "analytics": Category.ANALYTICS_PROFILE, "support": Category.SUPPORT_MESSAGE}


@dataclass(frozen=True)
class Activity:
    activity_id: str
    event_time: datetime
    event_type: str
    source_system: str
    target_system: str
    resource_id: str
    reported_result: str
    details: str


@dataclass(frozen=True)
class CatalogLink:
    activity_id: str
    event_time: datetime
    resource_id: str
    label: str              # identifier in parentheses (often the resource id, sometimes an external reference)
    email: str
    user_id: str
    exclusive: bool         # "belongs only to" the subject (e.g. an attachment)


def load_activities(data_dir):
    with open(Path(data_dir) / "system_activity.csv", newline="", encoding="utf-8") as f:
        return [Activity(r["activity_id"], parse_ts(r["event_time"]), r["event_type"], r["source_system"],
                         r["target_system"], r["resource_id"], r["reported_result"], r["details"])
                for r in csv.DictReader(f)]


def _obs(a, rid, category, state):
    return Observation(a.activity_id, a.event_time, a.event_time, system_for(rid) or a.target_system, rid,
                       category, state, link_keys_from(a.details), resource_refs_from(a.details, exclude=rid),
                       source=f"activity:{a.event_type}")


def observations(activities):
    out = []
    for a in activities:
        if a.event_type == "CHECK_DATA_FLOW" and "remains enabled" in a.details:
            out.append(_obs(a, a.resource_id, Category.DATA_FLOW, State.FLOW_ACTIVE))
        elif a.event_type == "CHECK_RESTORE_ACCESS" and "can still be restored" in a.details:
            out.append(_obs(a, a.resource_id, Category.BACKUP_ARCHIVE, State.RESTORE_ALLOWED))
        m = REPOPULATED_RE.search(a.details)
        if m and a.reported_result == "SUCCESS":
            target = m.group("rid")
            category = CATEGORY_BY_PREFIX.get(re.sub(r"_\d+$", "", target))
            if category:
                out.append(_obs(a, target, category, State.PRESENT if category != Category.ANALYTICS_PROFILE else State.IDENTIFIABLE))
            if a.resource_id.startswith("data_flow_"):
                out.append(_obs(a, a.resource_id, Category.DATA_FLOW, State.FLOW_ACTIVE))
            elif a.resource_id.startswith("backup_"):
                out.append(_obs(a, a.resource_id, Category.BACKUP_ARCHIVE, State.RESTORE_ALLOWED))
    return out


def catalog_links(activities):
    links = []
    for a in activities:
        if a.event_type != "LINK_RESOURCE_IDENTITY":
            continue
        m = CONFIRMED_RE.search(a.details) or LINK_RE.search(a.details)
        if m:
            links.append(CatalogLink(a.activity_id, a.event_time, m.group("rid"), m.group("label"),
                                     norm_email(m.group("email").rstrip(".")), m.group("user"),
                                     "belongs only to" in a.details))
    return links
