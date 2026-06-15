"""Password hashing using bcrypt directly.

Migrated off passlib (TMX-CI-BCRYPT). passlib 1.7.4 is unmaintained (last
release 2020) and incompatible with bcrypt 4.1+, which removed
`bcrypt.__about__`: passlib's backend self-test hashes a >72-byte probe that
bcrypt 4.x rejects, so passlib marks the bcrypt backend unusable and EVERY
`hash()` call fails with a spurious "password cannot be longer than 72 bytes"
error. That broke the demo-admin seed in CI (and would break login/register on
any fresh deploy that pulls bcrypt 4.x).

bcrypt produces the same `$2b$` hashes passlib did, so previously-stored hashes
verify unchanged (proven: a passlib-made hash passes `bcrypt.checkpw`).
"""
import bcrypt

# bcrypt only consumes the first 72 bytes of the password and bcrypt 4.x RAISES
# on longer input. Truncate to 72 bytes to (a) accept arbitrarily long passwords
# and (b) match the historical passlib/bcrypt truncation so older stored hashes
# still verify.
_MAX_BCRYPT_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw = plain_password.encode("utf-8")[:_MAX_BCRYPT_BYTES]
    try:
        return bcrypt.checkpw(pw, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # A malformed / non-bcrypt stored hash must fail closed, not crash auth.
        return False
