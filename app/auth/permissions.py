"""
Permission & Role definitions for TransMax RBAC.

Flat permission matrix with 6 pharma-appropriate roles.
"""
from enum import Enum
from typing import Set, Dict


class Permission(str, Enum):
    # Documents
    DOCUMENT_READ = "document:read"
    DOCUMENT_CREATE = "document:create"
    DOCUMENT_UPDATE = "document:update"
    DOCUMENT_DELETE = "document:delete"

    # Translation
    TRANSLATE_EXECUTE = "translate:execute"
    TRANSLATE_UPLOAD = "translate:upload"

    # Segments
    SEGMENT_READ = "segment:read"
    SEGMENT_EDIT = "segment:edit"

    # Review & Approval
    REVIEW_APPROVE = "review:approve"
    REVIEW_REJECT = "review:reject"

    # Knowledge / Black Book
    KNOWLEDGE_READ = "knowledge:read"
    KNOWLEDGE_MANAGE = "knowledge:manage"
    # TMX-3045 / Pillar 1: signed promotion of a learned rule from PROPOSED
    # to ACTIVE. Strictly stronger than KNOWLEDGE_MANAGE — KNOWLEDGE_MANAGE
    # lets a curator create or edit rules manually, but ONLY a holder of
    # RULE_APPROVE may flip a learned (LLM-extracted) rule to ACTIVE.
    RULE_APPROVE = "rule:approve"

    # Audit
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # Tools
    TOOLS_USE = "tools:use"

    # Admin
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    SYSTEM_ADMIN = "system:admin"


class UserRole(str, Enum):
    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    TRANSLATOR = "translator"
    REVIEWER = "reviewer"
    CURATOR = "curator"
    VIEWER = "viewer"


# Flat permission matrix
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: set(Permission),  # All permissions

    UserRole.PROJECT_MANAGER: {
        Permission.DOCUMENT_READ, Permission.DOCUMENT_CREATE,
        Permission.DOCUMENT_UPDATE, Permission.DOCUMENT_DELETE,
        Permission.TRANSLATE_EXECUTE, Permission.TRANSLATE_UPLOAD,
        Permission.SEGMENT_READ, Permission.SEGMENT_EDIT,
        Permission.REVIEW_APPROVE, Permission.REVIEW_REJECT,
        Permission.KNOWLEDGE_READ, Permission.KNOWLEDGE_MANAGE,
        Permission.RULE_APPROVE,  # TMX-3045: PMs may sign rule promotions.
        Permission.AUDIT_READ, Permission.AUDIT_EXPORT,
        Permission.TOOLS_USE, Permission.USERS_READ,
    },

    UserRole.TRANSLATOR: {
        Permission.DOCUMENT_READ, Permission.DOCUMENT_CREATE,
        Permission.DOCUMENT_UPDATE,
        Permission.TRANSLATE_EXECUTE, Permission.TRANSLATE_UPLOAD,
        Permission.SEGMENT_READ, Permission.SEGMENT_EDIT,
        Permission.KNOWLEDGE_READ,
        Permission.AUDIT_READ,
        Permission.TOOLS_USE,
    },

    UserRole.REVIEWER: {
        Permission.DOCUMENT_READ,
        Permission.SEGMENT_READ,
        Permission.REVIEW_APPROVE, Permission.REVIEW_REJECT,
        Permission.KNOWLEDGE_READ,
        Permission.AUDIT_READ, Permission.AUDIT_EXPORT,
        Permission.TOOLS_USE,
    },

    UserRole.CURATOR: {
        Permission.DOCUMENT_READ,
        Permission.SEGMENT_READ,
        Permission.KNOWLEDGE_READ, Permission.KNOWLEDGE_MANAGE,
        Permission.RULE_APPROVE,  # TMX-3045: curators are the canonical rule approvers.
        Permission.AUDIT_READ,
        Permission.TOOLS_USE,
    },

    UserRole.VIEWER: {
        Permission.DOCUMENT_READ,
        Permission.SEGMENT_READ,
        Permission.KNOWLEDGE_READ,
        Permission.AUDIT_READ,
        Permission.TOOLS_USE,
    },
}


def has_permission(role: UserRole, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())
