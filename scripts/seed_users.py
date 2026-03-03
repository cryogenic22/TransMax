#!/usr/bin/env python3
"""
Seed default users for TransMax auth.

Usage:
    python scripts/seed_users.py

Creates a default admin user for JWT mode:
    email: admin@transmax.local
    password: admin123
    role: admin

Only runs when AUTH_MODE=jwt. Safe to run multiple times (idempotent).
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def seed():
    if getattr(settings, "auth_mode", "none") != "jwt":
        print(f"AUTH_MODE={getattr(settings, 'auth_mode', 'none')} — seed only runs in JWT mode.")
        print("Set AUTH_MODE=jwt in your .env to enable local auth.")
        return

    from app.core.database import engine, SessionLocal
    from app.models.database import Base
    from app.models.auth import User
    from app.auth.password import hash_password
    from app.auth.permissions import UserRole

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Default admin
        existing = db.query(User).filter(User.email == "admin@transmax.local").first()
        if existing:
            print(f"Admin user already exists (id={existing.id})")
        else:
            admin = User(
                email="admin@transmax.local",
                name="TransMax Admin",
                hashed_password=hash_password("admin123"),
                role=UserRole.ADMIN.value,
                auth_provider="local",
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print(f"Created admin user: admin@transmax.local / admin123 (id={admin.id})")

        # Default demo users (optional)
        demo_users = [
            ("translator@transmax.local", "Translator Demo", "demo123", UserRole.TRANSLATOR),
            ("reviewer@transmax.local", "Reviewer Demo", "demo123", UserRole.REVIEWER),
            ("viewer@transmax.local", "Viewer Demo", "demo123", UserRole.VIEWER),
        ]
        for email, name, password, role in demo_users:
            exists = db.query(User).filter(User.email == email).first()
            if not exists:
                user = User(
                    email=email,
                    name=name,
                    hashed_password=hash_password(password),
                    role=role.value,
                    auth_provider="local",
                    is_active=True,
                )
                db.add(user)
                print(f"Created {role.value}: {email} / {password}")

        db.commit()
        print("\nSeed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
