"""Record → Observation rules shared by the SQL and record-file loaders (plan/phases/phase4.md §2.2).

The same collections appear in SQL snapshots (typed tables or record_json), snapshot bundles, and service
exports, under slightly different names. Each collection maps to one category and a state rule.
"""

from evidence.model import Category, Observation, State, link_keys_from, resource_refs_from, system_for
from identity import extract_emails

IDENTITY_FIELDS = ("user_id", "customer_reference", "email", "phone", "email_hash")
REQUESTER_FIELDS = ("requester_email", "requester_name", "requester_phone")
TOMBSTONE_PROHIBITED = ("name", "email", "phone", "email_hash")

PROFILE = {"customer_profiles", "customer_profiles_primary", "customer_profiles_failover_replica"}
SEARCH = {"customer_search_documents", "search_documents_primary"}
ANALYTICS = {"customer_analytics_profiles", "customer_analytics_reports", "profiles"}
SUPPORT_TICKETS = {"support_records", "tickets"}
EXPORTS = {"customer_exports", "exports", "customer_export_jobs"}
FLOWS = {"connector_subscriptions", "connectors", "connector_configurations"}
BACKUPS = {"backup_restore_entries", "restore_entries", "backup_catalog"}
AUDIT = {"security_audit_records", "security_audit_events", "audit_records"}
LEDGERS = {"operational_record_history", "ledger", "handover_check"}

LEDGER_STATE = {
    "FOUND": State.PRESENT,
    "NOT_FOUND": State.ABSENT,
    "IDENTIFIABLE": State.IDENTIFIABLE,
    "ANONYMIZED": State.ANONYMIZED,
    "REDACTED": State.REDACTED,
    "DISABLED": State.FLOW_DISABLED,
    "BLOCKED": State.RESTORE_BLOCKED,
}


def truthy(value):
    return value is True or str(value).strip().lower() in ("1", "true", "yes")


def _filled(record, fields):
    return any(record.get(f) not in (None, "") for f in fields)


def _obs(ctx, record, resource_id, category, state, extra_keys=frozenset()):
    return Observation(
        evidence_id=ctx["evidence_id"],
        file_captured_at=ctx["file_captured_at"],
        observed_at=ctx["observed_at"],
        system_id=system_for(resource_id) or ctx.get("system_hint") or "",
        resource_id=resource_id,
        category=category,
        state=state,
        link_keys=link_keys_from(record) | extra_keys,
        refs=resource_refs_from(record, exclude=resource_id),
        source=ctx.get("source", ""),
    )


def ledger_state(record_type, result):
    if result == "ACTIVE":
        return State.RESTORE_ALLOWED if record_type == "BACKUP_ARCHIVE" else State.FLOW_ACTIVE
    return LEDGER_STATE.get(result)


def observe(collection, record, ctx):
    """Observations for one record of `collection`. ctx: evidence_id, file_captured_at, observed_at, source."""
    rid = record.get("resource_id")
    if collection in LEDGERS:
        rtype, result = record.get("record_type"), record.get("result")
        state = ledger_state(rtype, result)
        if not rid or state is None:
            return []
        try:
            category = Category(rtype) if rtype != "DATA_FLOW" else Category.DATA_FLOW
        except ValueError:
            category = None
        return [_obs(ctx, record, rid, category, state)]
    if not rid:
        return []
    if collection in PROFILE:
        return [_obs(ctx, record, rid, Category.USER_PROFILE, State.PRESENT)]
    if collection in SEARCH:
        return [_obs(ctx, record, rid, Category.SEARCH_INDEX_ENTRY, State.PRESENT)]
    if collection in ANALYTICS:
        state = State.IDENTIFIABLE if _filled(record, IDENTITY_FIELDS) else State.ANONYMIZED
        return [_obs(ctx, record, rid, Category.ANALYTICS_PROFILE, state)]
    if collection in SUPPORT_TICKETS:
        state = State.IDENTIFIABLE if _filled(record, REQUESTER_FIELDS) else State.REDACTED
        return [_obs(ctx, record, rid, Category.SUPPORT_MESSAGE, state)]
    if collection == "support_conversations":
        text = record.get("message_text") or ""
        state = State.IDENTIFIABLE if extract_emails(text) else State.REDACTED
        return [_obs(ctx, record, rid, Category.SUPPORT_MESSAGE, state)]
    if collection == "ticket_attachments":
        return [_obs(ctx, record, rid, Category.SUPPORT_ATTACHMENT, State.PRESENT)]
    if collection in EXPORTS:
        available = record.get("download_available", True)
        return [_obs(ctx, record, rid, Category.USER_EXPORT, State.PRESENT if truthy(available) else State.ABSENT)]
    if collection in FLOWS:
        state = State.FLOW_ACTIVE if truthy(record.get("enabled")) else State.FLOW_DISABLED
        return [_obs(ctx, record, rid, Category.DATA_FLOW, state)]
    if collection in BACKUPS:
        state = State.RESTORE_ALLOWED if truthy(record.get("restore_allowed")) else State.RESTORE_BLOCKED
        return [_obs(ctx, record, rid, Category.BACKUP_ARCHIVE, state)]
    if collection in AUDIT:
        return [_obs(ctx, record, rid, Category.SECURITY_AUDIT_LOG, State.PRESENT)]
    if collection == "retained_order_records":
        return [_obs(ctx, record, rid, Category.LEGAL_HOLD_RECORD, State.PRESENT)]
    if collection == "deleted_customer_references":
        state = State.IDENTIFIABLE if _filled(record, TOMBSTONE_PROHIBITED) else State.REDACTED
        return [_obs(ctx, record, rid, Category.ACCOUNT_TOMBSTONE, state)]
    if collection == "profile_lookups":
        status = str(record.get("status_code"))
        state = State.ABSENT if status == "404" else State.PRESENT
        return [_obs(ctx, record, rid, Category.USER_PROFILE, state)]
    if collection == "index_queries":
        out = []
        query_keys = link_keys_from(record.get("query"))
        for doc in (record.get("hits") or {}).get("documents", []):
            if doc.get("resource_id"):
                out.append(_obs(ctx, doc, doc["resource_id"], Category.SEARCH_INDEX_ENTRY, State.PRESENT, query_keys))
        return out
    return []
