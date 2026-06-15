"""TMX-CI-BCRYPT — bcrypt password hashing (migrated off the unmaintained passlib).

Pins: a fresh hash round-trips, wrong passwords fail, an existing passlib-era
`$2b$` hash still verifies (no forced re-hash of stored credentials), long
passwords don't raise, and a malformed stored hash fails closed.
"""

from app.auth.password import hash_password, verify_password


def test_hash_then_verify_roundtrip():
    h = hash_password("S33d-pw!")
    assert h.startswith("$2b$")
    assert h != "S33d-pw!"  # not stored in plaintext
    assert verify_password("S33d-pw!", h) is True


def test_wrong_password_rejected():
    h = hash_password("correct-horse")
    assert verify_password("wrong-horse", h) is False


def test_existing_passlib_bcrypt_hash_still_verifies():
    # FROZEN regression pin: a real hash of "S33d-pw!" produced by the OLD
    # passlib.CryptContext(schemes=["bcrypt"]) path. Stored credentials written
    # before the migration MUST keep verifying (no forced DB re-hash). If this
    # ever fails, the migration would lock out every existing user.
    passlib_legacy = "$2b$12$X.ILpBNpaArLDJIXyv6FOuPJqjj3CPtyFfcG2kYSqgxpO5QXuxmOG"
    assert verify_password("S33d-pw!", passlib_legacy) is True
    assert verify_password("wrong", passlib_legacy) is False


def test_long_password_does_not_raise():
    # bcrypt 4.x raises on >72 bytes; we truncate, so this must not blow up.
    long_pw = "x" * 200
    h = hash_password(long_pw)
    assert verify_password(long_pw, h) is True
    # The first 72 bytes are what bcrypt uses, so a same-72-prefix verifies.
    assert verify_password("x" * 72 + "different-tail", h) is True


def test_malformed_stored_hash_fails_closed():
    assert verify_password("anything", "not-a-bcrypt-hash") is False
    assert verify_password("anything", "") is False
