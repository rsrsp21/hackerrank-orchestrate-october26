"""Tests for code/identity.py: resolution, as-of identifier sets, decoys, and normalizers."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from identity import (  # noqa: E402
    IdentityError,
    IdentityResolver,
    extract_emails,
    is_sha256,
    load_identity_tables,
    norm_email,
    norm_phone,
    parse_ts,
    sha256_email,
)

AUDIT_AT = parse_ts("2026-10-01T12:00:00Z")


@pytest.fixture(scope="module")
def tables():
    return load_identity_tables(ROOT / "dataset")


@pytest.fixture(scope="module")
def resolver(tables):
    return IdentityResolver(*tables)


def test_current_email_match(resolver):
    s = resolver.resolve("amina.elmasri@gmail.com", AUDIT_AT)
    assert (s.user_id, s.match, s.match_audit_id) == ("user_01", "current", None)


@pytest.mark.parametrize("email,user_id,audit_id", [
    ("nadia.ionescu@yahoo.com", "user_10", "audit_121"),
    ("noah.f438085@outlook.com", "user_29", "audit_284"),
    ("camille.bernard86@outlook.com", "user_30", "audit_280"),
])
def test_historical_email_match(resolver, email, user_id, audit_id):
    s = resolver.resolve(email, AUDIT_AT)
    assert (s.user_id, s.match, s.match_audit_id) == (user_id, "historical", audit_id)


def test_identifier_set_includes_old_values(resolver):
    s = resolver.resolve("haruka.s1838@zoho.com", AUDIT_AT)
    assert s.user_id == "user_11"
    assert {"haruka.s1838@zoho.com", "haruka.s183889@zoho.com"} <= s.emails
    assert {"819076102507", "819061560005"} <= s.phones
    assert "532f8531fceba1d914b95e331ffb690ebb2a2d64611ea00361df48bd919544b7" in s.email_hashes  # old hash
    assert sha256_email("haruka.s1838@zoho.com") in s.email_hashes
    assert ("user", "user_11") in s.link_keys()


def test_email_chain_collects_every_email(resolver):
    s = resolver.resolve("nadia.ionescu@yahoo.com", AUDIT_AT)
    assert len(s.emails) == 3


def test_input_is_case_and_space_insensitive(resolver):
    assert resolver.resolve("  AMINA.ElMasri@Gmail.COM ", AUDIT_AT).user_id == "user_01"


@pytest.mark.parametrize("email", ["g.silva76.jr@gmail.com", "nadia.popescu@yahoo.com", "nobody@example.com"])
def test_decoys_and_unknown_emails_do_not_resolve(resolver, email):
    with pytest.raises(IdentityError):
        resolver.resolve(email, AUDIT_AT)


def _synthetic():
    identities = [{"user_id": "user_x", "name": "Test Person", "email": "new@example.com", "phone": "+1 (555) 000-0002",
                   "email_hash": sha256_email("new@example.com"), "updated_at": "2026-06-01T00:00:00Z"}]
    audit = [
        {"audit_id": "a1", "user_id": "user_x", "event_time": "2026-05-01T00:00:00Z", "field_name": "email",
         "old_value": "old@example.com", "new_value": "new@example.com"},
        {"audit_id": "a2", "user_id": "user_x", "event_time": "2026-05-01T00:00:00Z", "field_name": "email_hash",
         "old_value": sha256_email("old@example.com"), "new_value": sha256_email("new@example.com")},
        {"audit_id": "a3", "user_id": "user_x", "event_time": "2026-05-01T00:00:00Z", "field_name": "phone",
         "old_value": "+1 555 000 0001", "new_value": "+1 (555) 000-0002"},
    ]
    return IdentityResolver(identities, audit)


def test_change_after_as_of_is_excluded():
    r = _synthetic()
    before = parse_ts("2026-04-01T00:00:00Z")
    s = r.resolve("old@example.com", before)
    assert s.match == "current"  # at as_of the old email was the live one
    assert s.emails == {"old@example.com"}
    assert s.phones == {"15550000001"}
    assert s.email_hashes == {sha256_email("old@example.com")}
    with pytest.raises(IdentityError):  # the new email did not exist yet
        r.resolve("new@example.com", before)


def test_change_before_as_of_is_included():
    r = _synthetic()
    s = r.resolve("old@example.com", parse_ts("2026-07-01T00:00:00Z"))
    assert (s.match, s.match_audit_id) == ("historical", "a1")
    assert s.emails == {"old@example.com", "new@example.com"}
    assert s.phones == {"15550000001", "15550000002"}


def test_hash_algorithm_matches_every_user(tables):
    identities, _ = tables
    assert all(sha256_email(r["email"]) == r["email_hash"] for r in identities)


def test_normalizers():
    assert norm_phone("+55 11 96656-0765") == norm_phone("+55 (11) 96656 0765") == "5511966560765"
    assert norm_email("  O.ERIKSEN10@YAHOO.COM ") == "o.eriksen10@yahoo.com"
    assert extract_emails("Please send the update to A.B@Example.com. Thanks") == {"a.b@example.com"}
    assert is_sha256(sha256_email("x@y.z")) and not is_sha256("sha256:00ff")
