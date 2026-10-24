# Phase 3 — Identity Resolution

**Time box:** ~1.5h
**Goal:** turn each request's `email` into exactly one `user_id` plus the full set of identifiers that user had **at or before `audit_at`**, with provenance, so Phase 4 can link evidence to the subject exactly (never fuzzily).
**Governing docs:** constitution Part II Phase 3; guardrails P3 + §5 Identity; data_notes §1.4, §2.4.

---

## 1. Entry gate
- [x] Hash algorithm confirmed: `email_hash = sha256(email)` (850/850; emails already lowercase).
- [x] Audit-log semantics documented: fields email / email_hash (always paired, same timestamp) / phone; no name changes; the latest `new_value` equals the current snapshot (302/302).
- [x] P2 exit gate met.

## 2. Facts this phase relies on

| Fact | Value | Source |
|---|---|---|
| Requests resolving via a **current** email | eval 418 + sample 29 = 447 | profile_csv.py, phase-3 check |
| Requests resolving **only via a historical** email (an audit `old_value`) | eval 100 + sample 3 = 103 | same |
| Unresolved / ambiguous | 0 / 0 | same |
| Current-email requesters who **also have history** (old emails/hashes/phones that evidence may still carry) | 93 | phase-3 check |
| Users with more than one email change (chains) | 2 | phase-3 check |
| Identity changes dated after a case's `requested_at` or `audit_at` | **0** (the temporal filter never changes a result here, but it must still be implemented for hidden tests) | phase-3 check |
| Phones shared across users | 0 | phase-3 check |
| Duplicate names | 3 pairs (decoys) → **names are never a link key** | profile_csv.py |
| Evidence identifier formats | emails in UPPERCASE (9+ rows), emails inside free text (support `message_text`, log `matched_value`), sha256 hashes (`email_hash`, `correlation_key`), phones in many formats (`+55 11 96656-0765`, `+1 (312) 555-0129`), `user_id` under several keys (`user_id`, `customer_reference`, `subject_reference`, `subject_ref`, `correlation_key`, `lookup_key`) | data_notes §2.4, §3 |
| Decoy user_ids not in user_identities (user_8741, user_9116, user_7204) and near-duplicate emails (`*.jr@…`, `nadia.popescu` vs `nadia.ionescu`, `g.silva76.jr`) | — | data_notes §2.4, §4 |

## 3. Design: `code/identity.py`

```python
@dataclass(frozen=True)
class Subject:
    user_id: str
    match: str                  # "current" | "historical"
    match_audit_id: str | None  # audit row that proves a historical match
    emails: frozenset[str]      # normalized: strip + lowercase
    email_hashes: frozenset[str]  # sha256 of every email + hashes recorded in the audit log
    phones: frozenset[str]      # digits only
    names: frozenset[str]       # display/explanation only, NEVER used for linking
    def link_keys(self) -> frozenset[tuple[str, str]]   # {("email",…), ("hash",…), ("phone",…), ("user",…)}

class IdentityResolver:
    def __init__(self, identities_rows, audit_rows): ...   # builds indexes once
    def resolve(self, email: str, as_of: datetime) -> Subject   # raises IdentityError if 0 or >1 users
```

Rules:
1. **Normalize** the request email (strip, lowercase, NFKC).
2. **Lookup order:** current snapshot email, then audit `old_value`/`new_value` for `field_name=email`, only for events with `event_time <= as_of`.
3. **Exactly one user** must match; otherwise raise `IdentityError` (logged, never guessed).
4. **Identifier set as of `as_of` (= audit_at):**
   - every value the user held at or before `as_of`: all `old_value`s of changes ≤ as_of, `new_value`s of changes ≤ as_of, and the snapshot value if no change to that field happened after `as_of`;
   - for a change dated after `as_of`: its `old_value` is the value at audit time (include it); its `new_value` and the current snapshot value did not exist yet (exclude them);
   - hashes: `sha256(email)` of every included email, plus audit `email_hash` values (cross-checked equal);
   - phones: digits-only of every included phone.
5. **Shared normalizers** (used by Phase 4 for evidence too): `norm_email`, `norm_phone` (digits only), `extract_emails(text)` (regex, for free text), `is_sha256`.
6. **Never link on names.** Names are kept only for human-readable explanations.

## 4. Tasks
- [x] 3.1 `code/identity.py` implemented (2026-10-24): `IdentityResolver.resolve(email, as_of)` → `Subject` (user_id, match, match_audit_id, emails, email_hashes, phones, names, `link_keys()`), raises `IdentityError` on 0 or >1 users; as_of-aware value sets; `load_identity_tables()` helper. Smoke run: eval 418 current / 100 historical / 0 errors; samples 29 / 3 / 0; chains handled (user_10 → 3 emails).
- [x] 3.2 (implemented with 3.1; tests pending in 3.3) Shared normalizers (`norm_email`, `norm_phone`, `extract_emails`, `sha256_email`) in `identity.py`, documented as the single source of truth for Phase 4 linking.
- [x] 3.3 Unit tests `code/tests/test_identity.py` (2026-10-24): **14 identity tests; the suite is 74/74 green**. The synthetic post-as_of test caught a real bug (an email live at as_of but changed later did not resolve); fixed by matching against the as_of value set and defining `current` = the value live at as_of. Eval/sample counts unchanged (418/100, 29/3). Covers:
  - current-email match (e.g. case_01 → user_01)
  - historical-email match with `match_audit_id` (case_10 → user_10 via audit_121; case_29 → user_29 via audit_284; case_30 → user_30 via audit_280)
  - identifier set includes old emails, old hashes, old phones (user_11: haruka.s183889@…, old hash, +81 90 6156 0005)
  - **synthetic** post-`as_of` change: the new value and snapshot value are excluded, the old value included
  - case-insensitive and whitespace-tolerant email input
  - unknown email → `IdentityError`; decoy `.jr` email does not resolve to the base user
  - phone normalization equality across formats
  - `sha256_email(current email) == email_hash` for every user (850/850)
- [x] 3.4 `code/explore/identity_report.py` (2026-10-24): eval **418 current / 100 historical / 0 errors**; samples **29 / 3 / 0** (case_10 via audit_121, case_29 via audit_284, case_30 via audit_280). Identifier-set sizes: eval 329 single-identity, 88 with 2 phones, 99 with 2 emails/hashes, 1 with 2+2, 1 with 3 emails (case_37 → user_35 chain).
  - **Subjects with more than one request** (each audited independently at its own `audit_at`): user_18 → case_52 (audit 06-19) and case_33 (07-19); user_07 → eval case_61 (02-14) and sample case_07 (09-12); user_17 → eval case_46 (03-11) and sample case_17 (09-15). The two eval/sample pairs show the same person at different times: useful for understanding, **never** copied as answers.
  - Email chains: user_10 (sample case_10) and user_35 (eval case_37), both resolved with all 3 emails.
- [ ] 3.5 Cross-check against the sample walkthrough: all 32 samples resolve to the user listed in `plan/sample_walkthrough.md` §3.
- [ ] 3.6 Update data_notes §1.4 with the final resolver semantics, and draft ≥1 custom case for Phase 6 (historical-email request where evidence exists only under the old email/hash).

## 5. Exit gate
- [ ] `code/identity.py` + tests exist; `uv run python -m pytest code/tests -q` all green (intent + identity).
- [ ] Resolution counts printed and equal to expectations (eval 418/100/0, samples 29/3/0).
- [ ] 32/32 sample subjects match the walkthrough.
- [ ] Unit tests cover current, historical, and post-`as_of` change cases.
- [ ] Committed.

## 6. Guardrail reminders
- Exact identifiers only: email (normalized), hash, phone (digits), user_id. **No fuzzy or name matching.**
- One request → exactly one user; raise and surface errors instead of guessing.
- Respect `as_of` even though no change here postdates an audit (hidden tests may).
- No prediction logic here: identity only. Evidence linking belongs to Phase 4.
