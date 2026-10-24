"""Log evidence → Observations.

Seven line formats (data_notes §3.3) are parsed into events {ts, service, trace, event, fields}. Events that
share a trace id are processed in order: identifiers from `*_started` lines (lookup_key, match_key, …) are
carried forward and attached to every outcome event with a resource_id in the same trace. Lines without a
trace id stand alone. Infrastructure noise produces no observation.
"""

import json
import re

from evidence.common import files_under
from evidence.interpret import ledger_state, truthy
from evidence.model import Category, Observation, State, link_keys_from, resource_refs_from, system_for
from identity import parse_ts

TS = r"(?P<ts>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)"
KV = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')
CARRIED = ("lookup_key", "match_key", "subject_key", "subject_ref", "owner_key", "correlation_key")


def _kv(text):
    out = {}
    for k, v in KV.findall(text):
        if v.startswith('"'):
            v = v[1:-1].replace('\\"', '"')
        out[k] = None if v == "null" else v
    return out


def parse_line(line):
    """One log line → (ts, service, trace, event, fields), or None for blank/unknown lines."""
    m = re.match(TS + r" \[\w+\] \[(?P<svc>[^\]]+)\] \[(?P<tr>[^\]]+)\] (?P<ev>\w+): ?(?P<rest>.*)$", line)
    if m:
        return m["ts"], m["svc"], m["tr"], m["ev"], _kv(m["rest"])
    m = re.match(TS + r" \| \w+ \| (?P<svc>[^|]+?) \| (?P<tr>[^|]+?) \| (?P<ev>[^|]+?) \| (?P<rest>.*)$", line)
    if m:
        return m["ts"], m["svc"], m["tr"], m["ev"], _kv(m["rest"])
    m = re.match(TS + r' requestId=(?P<tr>\S+) level=\w+ function=(?P<svc>\S+) message="(?P<msg>.*)"$', line)
    if m:
        f = _kv(m["msg"].replace('\\"', '"'))
        return m["ts"], m["svc"], m["tr"], f.pop("event", None), f
    m = re.match(TS + r" (?P<js>\{.*\})$", line)
    if m:
        f = json.loads(m["js"])
        return m["ts"], f.pop("service", None), f.get("trace_id"), f.pop("event", None), f
    m = re.match(TS + r" <\d+>\d+ \S+ (?P<svc>\S+) (?P<tr>\S+) - - (?P<rest>.*)$", line)
    if m:
        f = _kv(m["rest"])
        return m["ts"], m["svc"], m["tr"], f.pop("event", None), f
    m = re.match(TS + r" (?P<rest>.*)$", line)
    if m:
        f = _kv(m["rest"])
        return m["ts"], f.pop("service", None), f.get("trace_id"), f.pop("event", None), f
    return None


def _outcome(event, f):
    """(category, state) for an outcome event, or None if the event carries no data state."""
    if event == "profile_lookup_completed":
        absent = str(f.get("http_status")) == "404" or str(f.get("rows")) == "0"
        return Category.USER_PROFILE, State.ABSENT if absent else State.PRESENT
    if event == "index_query_completed":
        return (Category.SEARCH_INDEX_ENTRY, State.PRESENT) if f.get("result") == "hit" else (Category.SEARCH_INDEX_ENTRY, State.ABSENT)
    if event == "analytics_profile_read_completed":
        exposed = any(f.get(k) for k in ("customer_reference", "email", "phone", "email_hash"))
        return Category.ANALYTICS_PROFILE, State.IDENTIFIABLE if exposed else State.ANONYMIZED
    if event in ("analytics_profile_read", "analytics_identity_scan"):
        exposed = str(f.get("direct_identifiers", "0")) != "0"
        return Category.ANALYTICS_PROFILE, State.IDENTIFIABLE if exposed else State.ANONYMIZED
    if event == "contact_lookup_completed":
        return Category.CONTACT_RECORD, State.PRESENT if str(f.get("rows", "1")) != "0" else State.ABSENT
    if event == "support_ticket_read_completed":
        exposed = any(f.get(k) for k in ("requester_email", "requester_name", "requester_phone"))
        return Category.SUPPORT_MESSAGE, State.IDENTIFIABLE if exposed else State.REDACTED
    if event == "message_pii_scan":
        return Category.SUPPORT_MESSAGE, State.IDENTIFIABLE
    if event == "message_read":
        return Category.SUPPORT_MESSAGE, State.REDACTED if f.get("message_text") == "[REDACTED]" else State.IDENTIFIABLE
    if event == "attachment_pii_scan":
        return Category.SUPPORT_ATTACHMENT, State.PRESENT
    if event == "contact_query_completed":
        return Category.CONTACT_RECORD, State.PRESENT if str(f.get("rows", "1")) != "0" else State.ABSENT
    if event == "deletion_marker_check":
        return Category.CONTACT_RECORD, State.ABSENT if truthy(f.get("marker_found")) else State.PRESENT
    if event in ("connector_config_read_completed", "connector_heartbeat", "connector_config_loaded"):
        return Category.DATA_FLOW, State.FLOW_ACTIVE if truthy(f.get("enabled")) else State.FLOW_DISABLED
    if event == "restore_policy_read_completed":
        return Category.BACKUP_ARCHIVE, State.RESTORE_ALLOWED if truthy(f.get("restore_allowed")) else State.RESTORE_BLOCKED
    if event == "restore_candidate_evaluated":
        risky = truthy(f.get("eligible")) and not truthy(f.get("deletion_block"))
        return Category.BACKUP_ARCHIVE, State.RESTORE_ALLOWED if risky else State.RESTORE_BLOCKED
    if event == "restore_authorization_completed":
        return Category.BACKUP_ARCHIVE, State.RESTORE_BLOCKED if f.get("decision") == "deny" else State.RESTORE_ALLOWED
    if event in ("export_metadata_read_completed", "export_download_check_completed"):
        return Category.USER_EXPORT, State.PRESENT if truthy(f.get("available", "true")) else State.ABSENT
    if event == "audit_record_read_completed":
        return Category.SECURITY_AUDIT_LOG, State.PRESENT if str(f.get("rows", "1")) != "0" else State.ABSENT
    if event == "retained_order_loaded":
        return Category.LEGAL_HOLD_RECORD, State.PRESENT
    if event == "record_lookup":
        state = ledger_state(f.get("record_type"), f.get("result"))
        if state is None:
            return None
        try:
            return Category(f.get("record_type")), state
        except ValueError:
            return None, state
    return None


def parse_file(path):
    events = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        parsed = parse_line(line.rstrip())
        if parsed:
            ts, service, trace, event, fields = parsed
            events.append(dict(line=i, ts=parse_ts(ts), service=service, trace=trace or f"line-{i}", event=event, fields=fields))
    return events


def load(manifest):
    observations = []
    for ef in files_under(manifest, "logs", {".log"}):
        traces = {}
        for e in parse_file(ef.path):
            traces.setdefault(e["trace"], []).append(e)
        for trace, events in traces.items():
            carried = {}
            for e in events:
                f = e["fields"]
                carried.update({k: f[k] for k in CARRIED if f.get(k)})
                rid = f.get("resource_id")
                result = _outcome(e["event"], f) if rid else None
                if not result:
                    continue
                category, state = result
                observations.append(Observation(
                    evidence_id=ef.file_id,
                    file_captured_at=ef.captured_at,
                    observed_at=e["ts"],
                    system_id=system_for(rid) or e["service"] or "",
                    resource_id=rid,
                    category=category,
                    state=state,
                    link_keys=link_keys_from(f, carried),
                    refs=resource_refs_from(f, exclude=rid),
                    source=f"{ef.path.name}:{e['line']} {e['event']}",
                ))
    return observations
