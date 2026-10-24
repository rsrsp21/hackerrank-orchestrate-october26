"""Custom evaluation cases (plan/phases/phase6.md §2; reasoning in custom_cases.md).

Each case is a variant of a real request: `source` names the request it is built from (and replaces in its
isolated run), `changes` lists the fields that differ. Expectations were derived by hand from the rules and the
evidence before running the pipeline:
  exact_from   – the variant must reproduce the expected answer of this public sample (sample_output.csv)
  status       – expected deletion_status
  must_contain – partial steps (subset of fields) that must appear
  must_not     – partial steps that must not appear
"""

NA_TEXT_ES = "No quiero eliminar mi cuenta, solo cambiar el correo."
NA_TEXT_OPTOUT = "Please remove me from your mailing list."
NA_TEXT_RESTORE = "My account was deleted by mistake. Could you restore it?"
RETENTION_DELETE = ("I want my account closed and every trace of me removed. "
                    "Backups may be kept if they cannot restore my profile.")
OPTOUT_AND_DELETE = "Please unsubscribe me and delete my account entirely."

CUSTOM_CASES = [
    {"id": "cc_01", "title": "Spanish refusal with a deletion verb", "source": "case_533",
     "changes": {"request_text": NA_TEXT_ES}, "status": "NOT_APPLICABLE", "exact": []},
    {"id": "cc_02", "title": "Marketing opt-out phrased with 'remove'", "source": "case_533",
     "changes": {"request_text": NA_TEXT_OPTOUT}, "status": "NOT_APPLICABLE", "exact": []},
    {"id": "cc_03", "title": "Restore request that mentions deletion", "source": "case_533",
     "changes": {"request_text": NA_TEXT_RESTORE}, "status": "NOT_APPLICABLE", "exact": []},
    {"id": "cc_04", "title": "Deletion with retention clauses stays a deletion", "source": "case_17",
     "changes": {"request_text": RETENTION_DELETE}, "exact_from": "case_17"},
    {"id": "cc_05", "title": "Opt-out plus explicit deletion", "source": "case_21",
     "changes": {"request_text": OPTOUT_AND_DELETE}, "exact_from": "case_21"},
    {"id": "cc_06", "title": "Identity invariance: current email, evidence only under the old one", "source": "case_29",
     "changes": {"email": "noah.f4380@outlook.com"}, "exact_from": "case_29"},
    {"id": "cc_07", "title": "Historical email in mixed case", "source": "case_30",
     "changes": {"email": "Camille.Bernard86@Outlook.com"}, "exact_from": "case_30"},
    {"id": "cc_08", "title": "Identity change after audit_at (synthetic)", "unit_tests": [
        "code/tests/test_identity.py::test_change_after_as_of_is_excluded",
        "code/tests/test_identity.py::test_change_before_as_of_is_included"]},
    {"id": "cc_09", "title": "Ledger row recorded after the file capture is ignored", "source": "case_135",
     "changes": {},
     "must_contain": [{"operation": "VERIFY_RECORD_ABSENT", "resource_id": "account_1417"}],
     "must_not": [{"operation": "REPORT_REMAINING_RECORD", "resource_id": "account_1417"}]},
    {"id": "cc_10", "title": "Data recreated after deletion is reported once its evidence is usable", "source": "case_27",
     "changes": {"audit_at": "2026-09-17T12:00:00Z"}, "status": "INCOMPLETE",
     "must_contain": [{"phase": "FINDING", "operation": "REPORT_REMAINING_RECORD", "resource_id": "account_3866",
                       "evidence_id": "evidence_02"},
                      {"phase": "REMEDIATION", "operation": "DELETE_RECORD", "resource_id": "account_3866"}]},
    {"id": "cc_11", "title": "Legal hold is retained and verified, never deleted", "source": "case_261",
     "changes": {},
     "must_contain": [{"phase": "VERIFICATION", "operation": "VERIFY_RECORD_PRESENT", "system_id": "legal_service",
                       "resource_id": "legal_hold_8017"}],
     "must_not": [{"operation": "DELETE_RECORD", "resource_id": "legal_hold_8017"},
                  {"operation": "REDACT_RECORD", "resource_id": "legal_hold_8017"}]},
    {"id": "cc_12", "title": "Two-clock rule: audit before the inventory capture", "source": "case_09",
     "changes": {"audit_at": "2026-09-16T08:00:00Z"}, "status": "INCOMPLETE",
     "must_contain": [{"phase": "FINDING", "operation": "REPORT_RESTORE_RISK", "resource_id": "backup_4978",
                       "evidence_id": "activity_3709"}],
     "must_not": [{"evidence_id": "evidence_93"}, {"evidence_id": "evidence_06"}]},
]


def matches(step, partial):
    return all(step.get(k) == v for k, v in partial.items())
