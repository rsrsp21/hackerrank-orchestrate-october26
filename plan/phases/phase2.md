# Phase 2 — Request Intent Classification

**Time box:** ~1.5h (scheduled Oct 25 07:00–13:00 IST alongside P6; running early since P1 finished ahead of plan)
**Goal:** decide, from `request_text` alone, whether a request authorizes deletion. Non-deletion → `NOT_APPLICABLE` with `steps_json=[]`.
**Governing docs:** `plan/constitution.md` Part II Phase 2; `plan/guardrails.md` P2; `plan/data_notes.md` §1.3.

---

## 1. Entry gate
- [x] All distinct intent sentences and negation/override sentences catalogued (data_notes §1.3; listed in full in §3 below).
- [x] P1 exit gate met (2026-10-24).

## 2. What the data says

| Set | Texts | Shape | Deletion | Non-deletion |
|---|---|---|---|---|
| Eval (518) | template: 1 intent sentence + 1–2 boilerplate sentences | 12 English + 5 non-English intent sentences (pt, ko, es, ja, fr) | **508** | **10** (case_533–case_542, all reported NOT_STARTED) |
| Sample (32) | free conversational text (en, es, fr, ja) + some templates | richer phrasing, e.g. "I'm deleting my account. You can keep anonymous statistics…" | 32 | 0 |

- `CLASSIFY_REQUEST` activity rows (10) agree with the 10 non-deletion texts. They are **corroboration only**, never an input (constitution P2).
- **Traps in the non-deletion set:** deletion-like words used in a negated or limited sense:
  - "Please **remove** me from marketing lists **only**"
  - "This is an information request, **not a request to erase** it"
  - "**not asking for deletion**"
  - "please **don't delete** or change anything"
  - "**Do not close** the account"
  - "correct it **without removing** any of my records"
- **Traps in the deletion set** (from the samples): texts that *mention* keeping things but still authorize deletion:
  - "You can keep anonymous statistics" (case_04)
  - "Security records can stay" (case_23)
  - "You may retain backups if required" (case_17)
  - "keeping an internal deleted-account reference is fine" (case_31)
  - "the conversation itself may need to stay" (case_19)

  A naive "keep / retain / stay ⇒ non-deletion" rule would break these.

## 3. Full catalogue

**Deletion intent sentences in eval (all must → DELETION):**
1. Please treat this message as a request for permanent account deletion.
2. I would like to submit a request to delete this account and its personal data.
3. I am requesting deletion of the account registered to this email address.
4. Please erase the account linked to this email address.
5. I am asking you to remove my account and the personal information linked to it.
6. I no longer use this account and would like it permanently deleted.
7. Please permanently delete the account associated with this email address.
8. Please process a permanent account-deletion request for this email address.
9. Please close my account and process the associated personal-data deletion.
10. I would like the account associated with this address to be erased.
11. Please begin the deletion process for the account using this email address.
12. I want to close this account and have its associated personal data deleted.
13. (pt) Solicito a exclusão permanente da conta associada a este e-mail.
14. (ko) 이 이메일 주소에 연결된 계정의 영구 삭제를 요청합니다.
15. (es) Solicito la eliminación permanente de la cuenta asociada a este correo.
16. (ja) このメールアドレスに関連するアカウントの完全な削除を依頼します。
17. (fr) Je demande la suppression définitive du compte associé à cette adresse e-mail.

**Boilerplate sentences:** about 30 variants ("Please confirm…", "Please review identifiers…", "…deletion policy…"). They are neutral and must not flip the label. Note that some contain "deletion" ("Please apply the request across the systems covered by your deletion policy"), so the classifier must not decide on boilerplate alone.

**Non-deletion texts (all must → NOT_APPLICABLE):** case_533 phone update · 534 stop promotional emails · 535 portable download · 536 login reset · 537 surname correction · 538 marketing lists only · 539 what info you hold · 540 invoice copy · 541 change email · 542 copy of info.

## 4. Design (`code/intent.py`)

Deterministic, explainable, sentence-aware rules first, with an LLM fallback only for low-confidence texts (Phase 7).

```
classify(text) -> IntentResult(label: DELETION | NOT_APPLICABLE | UNSURE, cue: str, rule: str)
```
1. **Normalize:** NFKC, lowercase, typographic apostrophes → `'`, split sentences (`.`, `?`, `!`, `。`, `？`).
2. **Override (non-deletion) cues**, checked first, any language present:
   - explicit refusal: `not asking for deletion`, `not a request to (erase|delete)`, `(don't|do not) (delete|close|remove)`, `without removing`, `keep the account`, `leave (the|my) (account|profile)`, `continue using`, `still (use|need|want)` + account/service
   - scope limiter: `(remove|unsubscribe) … marketing … only`, `stop the promotional`
3. **Deletion cues:** (delete|deletion|erase|erasure|remove my account|close (my|this) account|permanently deleted|account-deletion|deleted my account|deleting my account) + es `eliminar|eliminación` + fr `suppression|supprimer` + pt `exclusão|excluir` + ja `削除` + ko `삭제`.
4. **Non-deletion topics** with no deletion cue: access/copy/download/export, correction/update/change, login/reset, invoice → NOT_APPLICABLE.
5. **Decision:**
   - override cue present → NOT_APPLICABLE (even if a deletion word is present)
   - else deletion cue in a non-boilerplate sentence → DELETION
   - else non-deletion topic → NOT_APPLICABLE
   - else UNSURE → LLM fallback (P7), defaulting to NOT_APPLICABLE only if the LLM is unavailable and no deletion cue appears anywhere
6. **Retention clauses** ("you can keep…", "may retain…", "can stay") are **not** override cues. They describe treatment, not intent.

## 5. Tasks
- [x] 2.1 `code/intent.py`: pure-function classifier. Override cues (en/es/fr/pt/ja/ko refusals, marketing-only, restore requests) → deletion cues in non-boilerplate sentences (incl. free-form: "remove … records/result", "profile is gone", "cannot identify me", wipe/purge) → non-deletion topics → UNSURE.
- [x] 2.2 `code/tests/test_intent.py`: **60 tests pass** (17 intent sentences × with/without boilerplate, boilerplate-only, 10 eval non-deletion + 6 hand traps, 5 extra deletions, all 32 samples, eval counts). pytest added as a uv dev dependency.
- [x] 2.3 Eval → **508 DELETION / 10 NOT_APPLICABLE / 0 UNSURE** (case_533–542, each with its override cue). Samples → 32/32 DELETION. The first rule version missed 5 free-form sample texts (UNSURE/NA); the cues were broadened, a generalization fix for hidden tests.
- [x] 2.4 Corroboration: the 10 CLASSIFY_REQUEST accounts map via the evidence_50 ledger email to exactly the 10 NOT_APPLICABLE cases (10/10). Not used as an input.
- [x] 2.5 `code/evaluation/custom_cases.md`: CC-01..CC-05 drafted (3 NOT_APPLICABLE traps + 2 deletion-with-trap cases).
- [x] 2.6 data_notes updated (§1.3).

## 6. Exit gate ✅ (2026-10-24)
- [x] Classifier module and tests exist; `uv run python -m pytest code/tests -q` → 60 passed.
- [x] Eval counts 508 / 10 / 0 with cues printed.
- [x] Samples 32/32 DELETION.
- [x] ≥3 custom intent cases drafted (5).
- [x] Committed.

## 7. Guardrail reminders
- Decide on `request_text` only: never `reported_status`, the email, case_id ranges (the 533–542 clustering is a coincidence of the data, not a feature), or activity rows.
- No LLM call for texts the rules decide confidently.
- Keep cue lists general (semantic patterns), not exact-sentence lookups, so hidden test texts still work.
