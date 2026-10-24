"""Identity resolution: request email -> one user_id plus every identifier held at or before audit_at.

Linking is exact only (normalized email, sha256 email hash, digits-only phone, user_id). Names are kept
for explanations and are never used to link evidence (duplicate names exist in the data).
The normalizers here are the single source of truth for evidence linking in later phases.
"""

import csv
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class IdentityError(Exception):
    """The request email resolves to no user or to more than one user."""


def parse_ts(value):
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


def norm_email(value):
    return unicodedata.normalize("NFKC", value).strip().lower()


def norm_phone(value):
    return re.sub(r"\D", "", value or "")


def sha256_email(email):
    return hashlib.sha256(norm_email(email).encode("utf-8")).hexdigest()


def extract_emails(text):
    return {norm_email(e) for e in EMAIL_RE.findall(text or "")}


def is_sha256(value):
    return isinstance(value, str) and bool(SHA256_RE.match(value.strip().lower()))


@dataclass(frozen=True)
class Subject:
    user_id: str
    match: str  # "current" | "historical"
    match_audit_id: str | None
    emails: frozenset
    email_hashes: frozenset
    phones: frozenset
    names: frozenset

    def link_keys(self):
        keys = {("user", self.user_id)}
        keys |= {("email", e) for e in self.emails}
        keys |= {("hash", h) for h in self.email_hashes}
        keys |= {("phone", p) for p in self.phones if p}
        return frozenset(keys)


class IdentityResolver:
    def __init__(self, identity_rows, audit_rows):
        self._current = {r["user_id"]: r for r in identity_rows}
        self._changes = {}
        for r in sorted(audit_rows, key=lambda r: (r["event_time"], r["audit_id"])):
            self._changes.setdefault(r["user_id"], []).append(r)
        # every email ever seen for a user -> candidate users (filtered by as_of in resolve)
        self._candidates = {}
        for r in identity_rows:
            self._candidates.setdefault(norm_email(r["email"]), set()).add(r["user_id"])
        for r in audit_rows:
            if r["field_name"] == "email":
                for v in (r["old_value"], r["new_value"]):
                    self._candidates.setdefault(norm_email(v), set()).add(r["user_id"])

    def _live_value(self, user_id, field, as_of):
        """The value of `field` in effect at as_of."""
        later = [c for c in self._changes.get(user_id, [])
                 if c["field_name"] == field and parse_ts(c["event_time"]) > as_of]
        return later[0]["old_value"] if later else self._current[user_id][field]

    def _match_audit_id(self, user_id, email, as_of):
        for c in self._changes.get(user_id, []):
            if c["field_name"] == "email" and parse_ts(c["event_time"]) <= as_of \
                    and email in (norm_email(c["old_value"]), norm_email(c["new_value"])):
                return c["audit_id"]
        return None

    def _values_as_of(self, user_id, field, as_of):
        """Every value of `field` the user held at or before as_of."""
        changes = [c for c in self._changes.get(user_id, []) if c["field_name"] == field]
        values = {c["old_value"] for c in changes}
        values |= {c["new_value"] for c in changes if parse_ts(c["event_time"]) <= as_of}
        if not any(parse_ts(c["event_time"]) > as_of for c in changes):
            values.add(self._current[user_id][field])
        return values

    def resolve(self, email, as_of):
        e = norm_email(email)
        users = {u for u in self._candidates.get(e, set())
                 if e in {norm_email(v) for v in self._values_as_of(u, "email", as_of)}}
        if len(users) != 1:
            raise IdentityError(f"{email!r} resolves to {len(users)} users as of {as_of.isoformat()}: {sorted(users)}")
        user_id = users.pop()
        match = "current" if e == norm_email(self._live_value(user_id, "email", as_of)) else "historical"
        emails = {norm_email(v) for v in self._values_as_of(user_id, "email", as_of)}
        hashes = {sha256_email(v) for v in emails}
        hashes |= {v.strip().lower() for v in self._values_as_of(user_id, "email_hash", as_of) if is_sha256(v)}
        phones = {norm_phone(v) for v in self._values_as_of(user_id, "phone", as_of)}
        return Subject(
            user_id=user_id,
            match=match,
            match_audit_id=None if match == "current" else self._match_audit_id(user_id, e, as_of),
            emails=frozenset(emails),
            email_hashes=frozenset(hashes),
            phones=frozenset(p for p in phones if p),
            names=frozenset({self._current[user_id]["name"]}),
        )


def load_identity_tables(data_dir):
    data_dir = Path(data_dir)
    with open(data_dir / "user_identities.csv", newline="", encoding="utf-8") as f:
        identities = list(csv.DictReader(f))
    with open(data_dir / "user_audit_log.csv", newline="", encoding="utf-8") as f:
        audit = list(csv.DictReader(f))
    return identities, audit
