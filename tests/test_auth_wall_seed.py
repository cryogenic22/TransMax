"""TMX-AUTH-WALL — demo-admin startup seed (flag-gated, idempotent, A3-safe)."""
from app.core.tenant_context import org_context


def _setup(core_db):
    from app.models.database import Base
    Base.metadata.create_all(bind=core_db.engine)
    core_db._seed_default_org()


def _count(core_db, email):
    from app.models.auth import User
    from app.models.database import DEFAULT_ORG_ID
    with org_context(DEFAULT_ORG_ID):
        s = core_db.SessionLocal()
        try:
            return s.query(User).filter(User.email == email).all()
        finally:
            s.close()


def test_seeds_demo_admin_when_enabled(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _setup(core_db)
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_mode", "jwt", raising=False)
    monkeypatch.setattr(settings, "seed_demo_admin", True, raising=False)
    monkeypatch.setattr(settings, "demo_admin_email", "seed@x.io", raising=False)
    monkeypatch.setattr(settings, "demo_admin_password", "S33d-pw!", raising=False)

    core_db._seed_demo_admin()
    core_db._seed_demo_admin()  # idempotent — must not duplicate

    rows = _count(core_db, "seed@x.io")
    assert len(rows) == 1
    assert rows[0].role == "admin"
    assert rows[0].hashed_password and rows[0].hashed_password != "S33d-pw!"  # hashed


def test_refuses_blank_password(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _setup(core_db)
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_mode", "jwt", raising=False)
    monkeypatch.setattr(settings, "seed_demo_admin", True, raising=False)
    monkeypatch.setattr(settings, "demo_admin_email", "np@x.io", raising=False)
    monkeypatch.setattr(settings, "demo_admin_password", "", raising=False)

    core_db._seed_demo_admin()
    assert len(_count(core_db, "np@x.io")) == 0  # A3: no blank-password account


def test_noop_when_not_jwt(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _setup(core_db)
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_mode", "none", raising=False)
    monkeypatch.setattr(settings, "seed_demo_admin", True, raising=False)
    monkeypatch.setattr(settings, "demo_admin_email", "x@x.io", raising=False)
    monkeypatch.setattr(settings, "demo_admin_password", "pw", raising=False)

    core_db._seed_demo_admin()  # must not raise and must not seed
    assert len(_count(core_db, "x@x.io")) == 0


def test_noop_when_flag_off(fresh_engine_for_db, monkeypatch):
    core_db = fresh_engine_for_db
    _setup(core_db)
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_mode", "jwt", raising=False)
    monkeypatch.setattr(settings, "seed_demo_admin", False, raising=False)
    monkeypatch.setattr(settings, "demo_admin_email", "off@x.io", raising=False)
    monkeypatch.setattr(settings, "demo_admin_password", "pw", raising=False)

    core_db._seed_demo_admin()
    assert len(_count(core_db, "off@x.io")) == 0
