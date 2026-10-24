"""Request intent classification: does request_text authorize deletion?

Deterministic, sentence-aware rules (plan/phases/phase2.md §4):
  1. override cues (explicit refusal / scope limiters) win -> NOT_APPLICABLE
  2. a deletion cue in a non-boilerplate sentence -> DELETION
  3. a non-deletion topic (access, export, correction, login, invoices, marketing) -> NOT_APPLICABLE
  4. otherwise UNSURE (resolved by the LLM fallback in a later phase)
Retention clauses ("you can keep anonymous statistics", "may retain backups") are not overrides:
they describe how data should be treated, not whether deletion is wanted.
"""

import re
import unicodedata
from dataclasses import dataclass

DELETION = "DELETION"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNSURE = "UNSURE"

# Explicit refusals or scope limiters. Checked first; any match means the text does not authorize deletion.
OVERRIDE_CUES = [
    r"\bnot (?:asking|requesting|looking) (?:for|to) (?:the )?(?:deletion|delete|erasure|erase|removal|remove)",
    r"\bnot a (?:deletion|erasure) request\b",
    r"\bnot a request to (?:erase|delete|remove|close)\b",
    r"\b(?:do not|don't|dont|never) (?:delete|erase|remove|close|deactivate)\b",
    r"\bwithout (?:removing|deleting|erasing|closing)\b",
    r"\b(?:keep|leave) (?:the|my|this) (?:account|profile)(?: \w+)? (?:as it is|active|open|in place)\b",
    r"\bleave (?:the|my) (?:account|profile)\b.*\b(?:active|in place|as it is)\b",
    r"\b(?:i )?(?:want|would like|need) to (?:continue|keep) using\b",
    r"\bi still (?:use|need) (?:it|the account|this account|my account)\b",
    r"\bmarketing (?:lists?|emails?|messages?|communications?) only\b",
    r"\bonly (?:from|the) marketing\b",
    r"\bremove me from (?:the |your |all )?(?:marketing|mailing|newsletter|promotional|email)\b(?!.*\b(?:delete|erase|close)\b)",
    # wants data or an account back rather than gone ("backups must not be able to restore" is not matched)
    r"\b(?:please|can you|could you|i want to|i'd like to|i would like to|help me) (?:restore|recover|reactivate|undo|reinstate|reopen)\b",
    # es / fr / pt / ja / ko refusals
    r"\bno (?:quiero|deseo) (?:eliminar|borrar|cerrar)\b",
    r"\bsin (?:eliminar|borrar)\b",
    r"\bne (?:demande|souhaite|veux) pas (?:la )?(?:suppression|supprimer|fermer)\b",
    r"\bsans supprimer\b",
    r"\bnão (?:quero|desejo|solicito) (?:a )?(?:exclusão|excluir|apagar)\b",
    r"削除しないで|削除は不要|削除を希望しません",
    r"삭제하지 ?마|삭제를 원하지 않",
]

# Deletion of the account / personal data, any language present in the data.
DELETION_CUES = [
    r"\b(?:delete|deleted|deleting|deletion)\b",
    r"\b(?:erase|erased|erasing|erasure)\b",
    r"\bremov(?:e|ed|ing|al)\b(?:\s+\w+){0,4}?\s+(?:account|profile|records?|data|details|information|traces?|copy|copies|results?|entries|entry|identifiers?|anything)\b",
    r"\b(?:account|profile|records?|data|details|information|traces?)\b(?:\s+\w+){0,6}?\s+(?:been |be |is |are |was |were )?removed\b",
    r"\b(?:wipe|purge|scrub)\b|\bget rid of\b|\bforget me\b|\bright to be forgotten\b",
    r"\bclean\b(?:\s+\w+){0,4}?\s+out\b",
    r"\b(?:profile|account|data) (?:is|are|was) (?:gone|removed)\b",
    r"\b(?:cannot|can't|can no longer|no longer) (?:identify|be linked to|point back to) me\b",
    r"\bclose (?:my|this|the) account\b",
    r"\bclose (?:it|the account) (?:completely|permanently)\b",
    r"\b(?:account|profile) closed\b",
    r"\b(?:closing|closed) (?:my|this|the) account\b",
    r"\baccount-deletion\b",
    r"\beliminar\b|\beliminación\b|\bborrar\b",
    r"\bsupprimer\b|\bsuppression\b|\beffacer\b",
    r"\bexclusão\b|\bexcluir\b|\bapagar\b",
    r"削除",
    r"삭제",
]

# Request types that are not deletion (used only when no deletion cue is present).
NON_DELETION_TOPICS = [
    r"\b(?:copy|download|export|portable|access)\b",
    r"\b(?:correct|correction|misspelled|update|out of date|change|replace)\b",
    r"\b(?:login|log in|password|reset)\b",
    r"\binvoices?\b|\breceipts?\b",
    r"\bwhat (?:personal )?(?:information|data)\b",
    r"\b(?:store|hold|keep|have) (?:on|about) me\b",
    r"\b(?:promotional|marketing|unsubscribe|newsletter)\b",
]

# Boilerplate that mentions deletion procedurally; a deletion cue found only here does not decide intent.
BOILERPLATE = [
    r"deletion policy",
    r"deletion procedure",
    r"retention and deletion requirements",
    r"eligible for deletion",
    r"scope of the deletion request",
    r"standard personal-data deletion",
]


@dataclass(frozen=True)
class IntentResult:
    label: str
    rule: str
    cue: str


def normalize(text):
    text = unicodedata.normalize("NFKC", text).lower()
    return text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?。？！])\s*", text) if s.strip()]


def _first(patterns, text):
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
    return None


def classify(text):
    norm = normalize(text)
    cue = _first(OVERRIDE_CUES, norm)
    if cue:
        return IntentResult(NOT_APPLICABLE, "override", cue)
    for s in sentences(norm):
        if _first(BOILERPLATE, s):
            continue
        cue = _first(DELETION_CUES, s)
        if cue:
            return IntentResult(DELETION, "deletion_cue", cue)
    cue = _first(NON_DELETION_TOPICS, norm)
    if cue:
        return IntentResult(NOT_APPLICABLE, "non_deletion_topic", cue)
    return IntentResult(UNSURE, "no_cue", "")
