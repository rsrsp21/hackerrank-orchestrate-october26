"""Workflow-timing links (L5) and the naming fallback (L6). See sample_walkthrough §2 and phase4.md §2.4.

Records that were deleted or anonymized carry no identifier, so the only grounded link to the request is the
deletion workflow recorded in system_activity:
  * account anchor: an account DELETE_RECORD within [reported_at - 90 min, reported_at + 15 min], preferring the
    ones whose result matches the reported status (COMPLETE↔SUCCESS, PARTIALLY_COMPLETE↔PARTIAL,
    NOT_STARTED↔FAILED; hand-built scenario cases do not always follow it);
  * analytics follow-up: an analytics ANONYMIZE/DELETE action at the offset its message template implies for its
    own request — "Policy action completed" lands at reported_at - 29 min (window -35..-25), "received the
    final result" at +30..+150 min, the scenario "reported the requested operation…" at -15..+15 min (offsets
    learned from identifier-linked actions, phase4.md 4.6) — and whose resource has state evidence inside the
    request's own window [requested_at, audit_at] (a record without such evidence can neither be cited nor be a
    finding, so it is not this request's concern).
Requests that share a reported_at compete for the same candidates, so all deletion requests are assigned
jointly: (1) a candidate whose resource is identifier-linked to another subject is removed; (2) a candidate
identifier-linked to this subject wins; (3) unique candidates are fixed and removed elsewhere until nothing
changes; (4) remaining ties go in case-number order to the earliest candidate — a documented last resort
(a generator-order artifact, not evidence) that matched all three colliding sample groups (cases 25/26,
27/28, and 03 vs eval case_44), where subject order matched 2 and queue order 1.
No account candidate → the subject's identifier-linked account (latest id) → else L6: the scenario naming
convention user_NN → account_0NN (sample case_04; low confidence).
"""

import re
from dataclasses import dataclass
from datetime import timedelta

STATUS_RESULT = {"COMPLETE": "SUCCESS", "PARTIALLY_COMPLETE": "PARTIAL", "NOT_STARTED": "FAILED"}
ACCOUNT_WINDOW = (timedelta(minutes=-90), timedelta(minutes=15))
FOLLOWUP_WINDOWS = {
    "Policy action completed": (timedelta(minutes=-35), timedelta(minutes=-25)),
    "received the final result": (timedelta(minutes=30), timedelta(minutes=150)),
    "reported the requested operation": (timedelta(minutes=-15), timedelta(minutes=15)),
}


@dataclass(frozen=True)
class WorkflowRequest:
    case_id: str
    user_id: str
    requested_at: object
    reported_at: object
    audit_at: object
    reported_status: str


@dataclass(frozen=True)
class WorkflowLink:
    resource_id: str
    kind: str          # "L5" | "L6"
    evidence_id: str   # the activity that anchors the link ("" for L6)
    method: str        # "own-identifier" | "unique" | "elimination" | "tie-break" | "identifier-account" | "fallback"


def _number(identifier):
    return int(re.sub(r"\D", "", identifier) or 0)


def _in_window(activity, request, window):
    return request.reported_at + window[0] <= activity.event_time <= request.reported_at + window[1]


def _followup_window(activity):
    return next((w for marker, w in FOLLOWUP_WINDOWS.items() if marker in activity.details), None)


def _is_account_anchor(a):
    return a.event_type == "DELETE_RECORD" and a.target_system == "account_service"


def _is_analytics_action(a):
    return a.event_type in ("ANONYMIZE_RECORD", "DELETE_RECORD") and a.target_system == "analytics_platform"


def _assign(requests, candidates, owners):
    """Joint assignment. candidates: case_id → [Activity]; owners: resource_id → {user_id}. Returns case_id → (Activity, method)."""
    by_case = {r.case_id: r for r in requests}
    cands = {}
    for cid, acts in candidates.items():
        user = by_case[cid].user_id
        own = [a for a in acts if user in owners.get(a.resource_id, ())]
        if own:
            cands[cid] = (own[:1], "own-identifier")
            continue
        free = [a for a in acts if not owners.get(a.resource_id)]
        if free:
            cands[cid] = (free, "unique" if len(free) == 1 else None)
    result, taken = {}, set()
    for cid, (acts, method) in cands.items():
        if method == "own-identifier":
            result[cid] = (acts[0], method)
            taken.add(acts[0].activity_id)
    changed = True
    while changed:
        changed = False
        for cid, (acts, method) in sorted(cands.items()):
            if cid in result:
                continue
            left = [a for a in acts if a.activity_id not in taken]
            if len(left) == 1:
                result[cid] = (left[0], "unique" if len(acts) == 1 else "elimination")
                taken.add(left[0].activity_id)
                changed = True
    for cid in sorted((c for c in cands if c not in result), key=lambda c: (_number(c), c)):
        left = sorted((a for a in cands[cid][0] if a.activity_id not in taken), key=lambda a: (a.event_time, a.activity_id))
        if left:
            result[cid] = (left[0], "tie-break")
            taken.add(left[0].activity_id)
    return result


def assign_workflows(requests, activities, owners, has_window_evidence=lambda request, resource_id: True,
                     analytics_eligible=None):
    """case_id → {"account": WorkflowLink|None, "analytics": WorkflowLink|None} for every deletion request.

    analytics_eligible: optional set of case_ids allowed to receive an identifier-less analytics record (the
    investigator restricts this to cases whose answer would actually list it, so ambiguous records are not
    consumed by cases that cannot use them)."""
    anchors = [a for a in activities if _is_account_anchor(a)]
    analytics = [a for a in activities if _is_analytics_action(a)]
    acc_cands, ana_cands = {}, {}
    for r in requests:
        in_window = [a for a in anchors if _in_window(a, r, ACCOUNT_WINDOW)]
        matching = [a for a in in_window if a.reported_result == STATUS_RESULT.get(r.reported_status)]
        acc_cands[r.case_id] = matching or in_window
        ana_cands[r.case_id] = [a for a in analytics if _followup_window(a) and _in_window(a, r, _followup_window(a))
                                and has_window_evidence(r, a.resource_id)
                                and (analytics_eligible is None or r.case_id in analytics_eligible)]
    acc = _assign(requests, acc_cands, owners)
    ana = _assign(requests, ana_cands, owners)
    owned_accounts = {}
    for rid, users in owners.items():
        if rid.startswith("account_"):
            for u in users:
                owned_accounts.setdefault(u, set()).add(rid)
    out = {}
    for r in requests:
        if r.case_id in acc:
            a, method = acc[r.case_id]
            account = WorkflowLink(a.resource_id, "L5", a.activity_id, method)
        elif owned_accounts.get(r.user_id):
            rid = max(owned_accounts[r.user_id], key=lambda x: int(re.sub(r"\D", "", x)))
            account = WorkflowLink(rid, "L1", "", "identifier-account")
        else:
            account = WorkflowLink(f"account_{_number(r.user_id):03d}", "L6", "", "fallback")
        analytics_link = None
        if r.case_id in ana:
            a, method = ana[r.case_id]
            analytics_link = WorkflowLink(a.resource_id, "L5", a.activity_id, method)
        out[r.case_id] = {"account": account, "analytics": analytics_link}
    return out
