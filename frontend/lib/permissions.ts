/**
 * Client-side mirror of backend ROLE_PERMISSIONS.
 * Used for UI-level gating (hiding buttons, menu items, etc.)
 * The backend is the source of truth — this is for UX only.
 */

export type UserRole = "admin" | "project_manager" | "translator" | "reviewer" | "curator" | "viewer";

export type Permission =
  | "document:read" | "document:create" | "document:update" | "document:delete"
  | "translate:execute" | "translate:upload"
  | "segment:read" | "segment:edit"
  | "review:approve" | "review:reject"
  | "knowledge:read" | "knowledge:manage"
  | "audit:read" | "audit:export"
  | "tools:use"
  | "users:read" | "users:manage" | "system:admin";

const ALL_PERMISSIONS: Permission[] = [
  "document:read", "document:create", "document:update", "document:delete",
  "translate:execute", "translate:upload",
  "segment:read", "segment:edit",
  "review:approve", "review:reject",
  "knowledge:read", "knowledge:manage",
  "audit:read", "audit:export",
  "tools:use",
  "users:read", "users:manage", "system:admin",
];

export const ROLE_PERMISSIONS: Record<UserRole, Set<Permission>> = {
  admin: new Set(ALL_PERMISSIONS),

  project_manager: new Set([
    "document:read", "document:create", "document:update", "document:delete",
    "translate:execute", "translate:upload",
    "segment:read", "segment:edit",
    "review:approve", "review:reject",
    "knowledge:read", "knowledge:manage",
    "audit:read", "audit:export",
    "tools:use", "users:read",
  ]),

  translator: new Set([
    "document:read", "document:create", "document:update",
    "translate:execute", "translate:upload",
    "segment:read", "segment:edit",
    "knowledge:read",
    "audit:read",
    "tools:use",
  ]),

  reviewer: new Set([
    "document:read",
    "segment:read",
    "review:approve", "review:reject",
    "knowledge:read",
    "audit:read", "audit:export",
    "tools:use",
  ]),

  curator: new Set([
    "document:read",
    "segment:read",
    "knowledge:read", "knowledge:manage",
    "audit:read",
    "tools:use",
  ]),

  viewer: new Set([
    "document:read",
    "segment:read",
    "knowledge:read",
    "audit:read",
    "tools:use",
  ]),
};

export function hasPermission(role: UserRole, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role]?.has(permission) ?? false;
}

export function hasRole(userRole: UserRole, allowedRoles: UserRole[]): boolean {
  return allowedRoles.includes(userRole);
}

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  project_manager: "Project Manager",
  translator: "Translator",
  reviewer: "Reviewer",
  curator: "Curator",
  viewer: "Viewer",
};

export const ROLE_COLORS: Record<UserRole, string> = {
  admin: "#ea4335",
  project_manager: "#4285f4",
  translator: "#34a853",
  reviewer: "#fbbc04",
  curator: "#9334e6",
  viewer: "#5f6368",
};
