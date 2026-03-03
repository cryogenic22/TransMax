"""
User model for TransMax auth.

Only created when AUTH_MODE != 'none'. Uses the same Base as other models
so create_all() picks it up automatically when the model is imported.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime

from app.models.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Null for SSO users

    role = Column(String(50), nullable=False, default="viewer")
    auth_provider = Column(String(50), nullable=False, default="local")  # local | okta | microsoft | google
    external_id = Column(String(255), nullable=True, index=True)  # SSO subject ID

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role={self.role})>"
