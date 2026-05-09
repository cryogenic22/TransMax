import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

/**
 * Next.js middleware for auth-based route protection.
 *
 * Behaviour:
 * - Public paths (/, /login, /_next, /api, static assets) are always allowed
 * - If a transmax_token cookie exists, request proceeds
 * - If no token AND the backend is in auth mode (jwt/oidc), redirect to /login
 * - If AUTH_MODE=none (or unknown), allow everything through
 *
 * The real auth validation happens server-side on each API call.
 * This middleware is a UX convenience to prevent flash-of-content.
 */

const PUBLIC_PATHS = ["/", "/login", "/_next", "/api", "/favicon.ico", "/health"]

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some(p => pathname === p || pathname.startsWith(p + "/") || pathname.startsWith("/_next"))
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Always allow public paths
  if (isPublic(pathname)) {
    return NextResponse.next()
  }

  // Check for auth token
  const token = request.cookies.get("transmax_token")?.value

  if (!token) {
    // No token — redirect to login
    // But only if we know auth is enabled. Since middleware runs before
    // the client can fetch /api/auth/config, we use a simple heuristic:
    // the NEXT_PUBLIC_AUTH_MODE env var (set at build time), defaulting to "none".
    const authMode = process.env.NEXT_PUBLIC_AUTH_MODE || "none"
    if (authMode !== "none") {
      const loginUrl = new URL("/login", request.url)
      loginUrl.searchParams.set("redirect", pathname)
      return NextResponse.redirect(loginUrl)
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    // Match all paths except static files and api routes
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
}
