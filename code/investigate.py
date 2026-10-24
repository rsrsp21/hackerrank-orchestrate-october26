"""Per-case investigation: who the subject is, which resources are theirs, and each resource's state at audit_at.

Pipeline per deletion request (phase4.md §2.5):
  subject (identity.py) → identifier links L1–L4 (linking.py, membership may use any evidence, Art. 3.5)
  → workflow account L5/L6 (workflow.py, assigned jointly over all requests)
  → state of each resource from evidence in [requested_at, audit_at] (EvidenceIndex.state_at)
  → required action per category and state.
Two passes: identifier-less anonymized analytics are only attributed among cases that are provisionally
COMPLETE, because only those answers list compliant records (an INCOMPLETE case cannot use them and must not
consume an ambiguous record that another case needs).
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path

from evidence.index import build
from evidence.model import Category, State, resource_prefix, system_for
from identity import IdentityError, IdentityResolver, load_identity_tables, parse_ts
from intent import DELETION, classify
from linking import identifier_links
from workflow import WorkflowRequest, assign_workflows

# (category, state) → action. "NONE" = already compliant; "RETAIN" = must stay present.
ACTIONS = {
    (Category.USER_PROFILE, State.PRESENT): "DELETE",
    (Category.SEARCH_INDEX_ENTRY, State.PRESENT): "DELETE",
    (Category.CONTACT_RECORD, State.PRESENT): "DELETE",
    (Category.SUPPORT_ATTACHMENT, State.PRESENT): "DELETE",
    (Category.USER_EXPORT, State.PRESENT): "DELETE",
    (Category.MARKETING_PROFILE, State.PRESENT): "DELETE",
    (Category.ANALYTICS_PROFILE, State.IDENTIFIABLE): "ANONYMIZE",
    (Category.ANALYTICS_PROFILE, State.PRESENT): "ANONYMIZE",
    (Category.SUPPORT_MESSAGE, State.IDENTIFIABLE): "REDACT",
    (Category.SUPPORT_MESSAGE, State.PRESENT): "REDACT",
    (Category.ACCOUNT_TOMBSTONE, State.IDENTIFIABLE): "REDACT",
    (Category.DATA_FLOW, State.FLOW_ACTIVE): "DISABLE",
    (Category.BACKUP_ARCHIVE, State.RESTORE_ALLOWED): "BLOCK",
}
COMPLIANT = {
    State.ABSENT: "ABSENT",
    State.ANONYMIZED: "ANONYMIZED",
    State.REDACTED: "REDACTED",
    State.FLOW_DISABLED: "DISABLED",
    State.RESTORE_BLOCKED: "BLOCKED",
}
RETAINED = {Category.SECURITY_AUDIT_LOG, Category.LEGAL_HOLD_RECORD}


@dataclass(frozen=True)
class ResourceState:
    system_id: str
    resource_id: str
    category: Category | None
    state: State | None
    evidence_id: str        # evidence that determines the state at audit_at ("" if none usable)
    link: str               # L1..L6 + method
    action: str             # DELETE | REDACT | ANONYMIZE | DISABLE | BLOCK | RETAIN | NONE | UNKNOWN
    compliant_state: str    # ABSENT | ANONYMIZED | REDACTED | DISABLED | BLOCKED | PRESENT | ""


@dataclass
class CaseInvestigation:
    case_id: str
    intent: str
    subject: object = None
    account: ResourceState | None = None
    resources: list = field(default_factory=list)   # non-account resources and extra subject accounts
    notes: list = field(default_factory=list)

    @property
    def findings(self):
        items = ([self.account] if self.account else []) + self.resources
        return [r for r in items if r.action in ("DELETE", "REDACT", "ANONYMIZE", "DISABLE", "BLOCK")]

    @property
    def status(self):
        if self.intent != DELETION:
            return "NOT_APPLICABLE"
        return "INCOMPLETE" if self.findings else "COMPLETE"


def _category(index, rid, state_obs):
    if state_obs is not None and state_obs.category is not None:
        return state_obs.category
    cats = [o.category for o in index.by_rid.get(rid, []) if o.category is not None]
    return max(set(cats), key=cats.count) if cats else (Category.USER_PROFILE if resource_prefix(rid) == "account" else None)


def resource_state(index, rid, request, link):
    audit_at, since = parse_ts(request["audit_at"]), parse_ts(request["requested_at"])
    obs = index.state_at(rid, audit_at, since)
    category = _category(index, rid, obs)
    if category in RETAINED:
        present = obs is not None and obs.state == State.PRESENT
        return ResourceState(system_for(rid), rid, category, obs.state if obs else None,
                             obs.evidence_id if present else "", link, "RETAIN", "PRESENT")
    if obs is None:
        return ResourceState(system_for(rid), rid, category, None, "", link, "UNKNOWN", "")
    action = ACTIONS.get((category, obs.state))
    if action:
        return ResourceState(system_for(rid), rid, category, obs.state, obs.evidence_id, link, action, "")
    return ResourceState(system_for(rid), rid, category, obs.state, obs.evidence_id, link, "NONE",
                         COMPLIANT.get(obs.state, ""))


def identity_conflict(index, rid, subject):
    """A catalog link is a claim. Reject it when the record's own evidence names people (emails/phones) and none of
    them is the subject (Q9: marketing_001 shows another person's identifiers while a catalog row links it to
    user_09). Records that carry no direct identifiers cannot contradict the link."""
    keys = subject.link_keys()
    direct = {k for o in index.by_rid.get(rid, []) for k in o.link_keys if k[0] in ("email", "phone")}
    return bool(direct) and not (direct & keys)


def load_requests(data_dir, names=("deletion_requests.csv", "sample_deletion_requests.csv")):
    rows = []
    for name in names:
        path = Path(data_dir) / name
        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                rows += list(csv.DictReader(f))
    return rows


def investigate_all(data_dir, requests=None, index=None):
    """case_id → CaseInvestigation for every request (deletion and non-deletion)."""
    index = index or build(data_dir)
    resolver = IdentityResolver(*load_identity_tables(data_dir))
    requests = requests if requests is not None else load_requests(data_dir)
    cases, links_by_case, wf_requests, owners = {}, {}, [], {}
    for r in requests:
        inv = CaseInvestigation(r["case_id"], classify(r["request_text"]).label)
        cases[r["case_id"]] = inv
        if inv.intent != DELETION:
            continue
        try:
            inv.subject = resolver.resolve(r["email"], parse_ts(r["audit_at"]))
        except IdentityError as exc:
            inv.notes.append(f"identity: {exc}")
            continue
        links = identifier_links(inv.subject, index, None)
        links_by_case[r["case_id"]] = links
        for rid in links:
            owners.setdefault(rid, set()).add(inv.subject.user_id)
        wf_requests.append(WorkflowRequest(r["case_id"], inv.subject.user_id, parse_ts(r["requested_at"]),
                                           parse_ts(r["reported_at"]), parse_ts(r["audit_at"]), r["reported_status"]))
    by_id = {r["case_id"]: r for r in requests}
    window = lambda req, rid: bool(index.usable(rid, req.audit_at, req.requested_at))  # noqa: E731

    # pass 1: accounts + identifier-linked resources → provisional status
    wf = assign_workflows(wf_requests, index.activities, owners, window, analytics_eligible=set())
    for req in wf_requests:
        inv, r = cases[req.case_id], by_id[req.case_id]
        acc = wf[req.case_id]["account"]
        inv.account = resource_state(index, acc.resource_id, r, f"{acc.kind}:{acc.method}")
        for rid, link in sorted(links_by_case[req.case_id].items()):
            if rid == acc.resource_id:
                continue
            if link.kind == "L4" and identity_conflict(index, rid, inv.subject):
                inv.notes.append(f"{rid}: catalog link {link.evidence_id} contradicted by the record's own identifiers")
                continue
            st = resource_state(index, rid, r, f"{link.kind}:{link.evidence_id}")
            if st.action == "UNKNOWN":
                continue
            if resource_prefix(rid) == "account" and st.action != "DELETE":
                continue  # other accounts matter only when still present (e.g. replica drift)
            inv.resources.append(st)

    # pass 2: identifier-less analytics only for provisionally COMPLETE cases
    eligible = {c for c, inv in cases.items() if inv.intent == DELETION and inv.subject and inv.status == "COMPLETE"
                and not any(x.category == Category.ANALYTICS_PROFILE for x in inv.resources)}
    wf2 = assign_workflows(wf_requests, index.activities, owners, window, analytics_eligible=eligible)
    for req in wf_requests:
        ana = wf2[req.case_id]["analytics"]
        inv = cases[req.case_id]
        if ana and ana.method != "own-identifier" and all(x.resource_id != ana.resource_id for x in inv.resources):
            st = resource_state(index, ana.resource_id, by_id[req.case_id], f"{ana.kind}:{ana.method}")
            if st.action != "UNKNOWN":
                inv.resources.append(st)
    for inv in cases.values():
        inv.resources.sort(key=lambda x: (x.system_id or "", x.resource_id))
    check_temporal(cases, by_id, index)
    return cases


def check_temporal(cases, requests_by_id, index):
    """Guard: every evidence chosen for a state must be usable in the case's window (two clocks + request window)."""
    for cid, inv in cases.items():
        r = requests_by_id[cid]
        audit_at, since = parse_ts(r["audit_at"]), parse_ts(r["requested_at"])
        for st in ([inv.account] if inv.account else []) + inv.resources:
            if not st.evidence_id:
                continue
            omission = index.omission(st.resource_id, audit_at, since)
            ok = (any(o.evidence_id == st.evidence_id for o in index.usable(st.resource_id, audit_at, since))
                  or (omission is not None and omission.evidence_id == st.evidence_id))
            if not ok:
                raise AssertionError(f"{cid}: {st.resource_id} cites {st.evidence_id} outside [requested_at, audit_at]")
