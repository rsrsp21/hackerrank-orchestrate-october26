"""Investigation → deletion_status + steps_json (plan/phases/phase5.md §3).

INCOMPLETE: FINDING per action item (cites the state evidence), REMEDIATION per action item, VERIFICATION for the
account, retained records, and every remediated item — remediation and verification carry evidence_id "".
COMPLETE: VERIFICATION only (account, retained records, already-compliant items), each citing its proof.
NOT_APPLICABLE: [].
Steps are sorted by phase, then operation order (problem statement table), then system_id, then resource_id.
"""

import json

FINDING, REMEDIATION, VERIFICATION = "FINDING", "REMEDIATION", "VERIFICATION"

# action → ((finding op, state), (remediation op, state), (verification op, state))
ACTION_STEPS = {
    "DELETE": (("REPORT_REMAINING_RECORD", "PRESENT"), ("DELETE_RECORD", "ABSENT"), ("VERIFY_RECORD_ABSENT", "ABSENT")),
    "REDACT": (("REPORT_EXPOSED_PII", "PRESENT"), ("REDACT_RECORD", "REDACTED"), ("VERIFY_RECORD_REDACTED", "REDACTED")),
    "ANONYMIZE": (("REPORT_EXPOSED_PII", "PRESENT"), ("ANONYMIZE_RECORD", "ANONYMIZED"),
                  ("VERIFY_RECORD_ANONYMIZED", "ANONYMIZED")),
    "DISABLE": (("REPORT_ACTIVE_DATA_FLOW", "ACTIVE"), ("DISABLE_DATA_FLOW", "DISABLED"),
                ("VERIFY_DATA_FLOW_DISABLED", "DISABLED")),
    "BLOCK": (("REPORT_RESTORE_RISK", "ACTIVE"), ("BLOCK_RESTORE", "BLOCKED"), ("VERIFY_RESTORE_BLOCKED", "BLOCKED")),
}
# compliant state of an already-treated record → its verification
COMPLIANT_VERIFICATION = {
    "ABSENT": ("VERIFY_RECORD_ABSENT", "ABSENT"),
    "PRESENT": ("VERIFY_RECORD_PRESENT", "PRESENT"),
    "REDACTED": ("VERIFY_RECORD_REDACTED", "REDACTED"),
    "ANONYMIZED": ("VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
    "DISABLED": ("VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
    "BLOCKED": ("VERIFY_RESTORE_BLOCKED", "BLOCKED"),
}
OPERATION_ORDER = {
    FINDING: ["REPORT_REMAINING_RECORD", "REPORT_EXPOSED_PII", "REPORT_ACTIVE_DATA_FLOW", "REPORT_RESTORE_RISK"],
    REMEDIATION: ["DISABLE_DATA_FLOW", "BLOCK_RESTORE", "DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD"],
    VERIFICATION: ["VERIFY_RECORD_ABSENT", "VERIFY_RECORD_PRESENT", "VERIFY_RECORD_REDACTED",
                   "VERIFY_RECORD_ANONYMIZED", "VERIFY_DATA_FLOW_DISABLED", "VERIFY_RESTORE_BLOCKED"],
}
PHASES = [FINDING, REMEDIATION, VERIFICATION]
# (phase, operation) → the only state allowed with it
ALLOWED = {}
for _find, _fix, _check in ACTION_STEPS.values():
    ALLOWED[(FINDING, _find[0])] = _find[1]
    ALLOWED[(REMEDIATION, _fix[0])] = _fix[1]
    ALLOWED[(VERIFICATION, _check[0])] = _check[1]
for _op, _state in COMPLIANT_VERIFICATION.values():
    ALLOWED[(VERIFICATION, _op)] = _state

# Policy for COMPLETE-case verifications that have no citable evidence (phase5.md §3.2 rule 7; decided in task 5.4).
ACCOUNT_WITHOUT_EVIDENCE = "empty"      # "empty" → keep the step with evidence_id ""; "omit" → drop it
RETAINED_WITHOUT_EVIDENCE = "omit"


def _step(phase, op_state, resource, evidence_id=""):
    op, state = op_state
    return {"phase": phase, "system_id": resource.system_id, "resource_id": resource.resource_id,
            "operation": op, "state": state, "evidence_id": evidence_id}


def _sort_key(step):
    return (PHASES.index(step["phase"]), OPERATION_ORDER[step["phase"]].index(step["operation"]),
            step["system_id"], step["resource_id"])


def steps_for(inv):
    """Ordered, numbered steps for one CaseInvestigation."""
    if inv.status == "NOT_APPLICABLE" or inv.account is None:
        return []
    items = [inv.account] + list(inv.resources)
    steps = []
    if inv.status == "INCOMPLETE":
        for r in items:
            if r.action in ACTION_STEPS:
                find, fix, check = ACTION_STEPS[r.action]
                steps += [_step(FINDING, find, r, r.evidence_id), _step(REMEDIATION, fix, r), _step(VERIFICATION, check, r)]
        if inv.account.action not in ACTION_STEPS:
            steps.append(_step(VERIFICATION, COMPLIANT_VERIFICATION["ABSENT"], inv.account))
        for r in inv.resources:
            if r.action == "RETAIN":
                steps.append(_step(VERIFICATION, COMPLIANT_VERIFICATION["PRESENT"], r))
    else:
        acc = inv.account
        if acc.evidence_id or ACCOUNT_WITHOUT_EVIDENCE == "empty":
            steps.append(_step(VERIFICATION, COMPLIANT_VERIFICATION["ABSENT"], acc, acc.evidence_id))
        for r in inv.resources:
            if r.action == "RETAIN":
                if r.evidence_id or RETAINED_WITHOUT_EVIDENCE == "empty":
                    steps.append(_step(VERIFICATION, COMPLIANT_VERIFICATION["PRESENT"], r, r.evidence_id))
            elif r.action == "NONE" and r.compliant_state in COMPLIANT_VERIFICATION:
                steps.append(_step(VERIFICATION, COMPLIANT_VERIFICATION[r.compliant_state], r, r.evidence_id))
    unique = {(s["phase"], s["operation"], s["system_id"], s["resource_id"]): s for s in steps}
    ordered = sorted(unique.values(), key=_sort_key)
    return [{"step_no": i, **s} for i, s in enumerate(ordered, 1)]


def serialize(steps):
    """Compact JSON with sorted keys (deterministic). The grader ignores key order; the sample file mixes orders."""
    return json.dumps(steps, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
