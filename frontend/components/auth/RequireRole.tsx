"use client"

import { useAuth } from "@/lib/auth"
import { UserRole, Permission } from "@/lib/permissions"

interface RequireRoleProps {
  roles?: UserRole[]
  permission?: Permission
  children: React.ReactNode
  fallback?: React.ReactNode
}

/**
 * Conditionally render children based on role or permission.
 * In no-auth mode, everything is visible (user is admin).
 */
export default function RequireRole({ roles, permission, children, fallback = null }: RequireRoleProps) {
  const { user, hasPermission, hasRole } = useAuth()

  if (!user) return <>{fallback}</>

  if (permission && !hasPermission(permission)) return <>{fallback}</>
  if (roles && roles.length > 0 && !hasRole(...roles)) return <>{fallback}</>

  return <>{children}</>
}
