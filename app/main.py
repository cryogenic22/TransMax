import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.endpoints import router as api_router
from app.api.documents import router as documents_router
from app.api.segments import router as segments_router
from app.api.auth import router as auth_router
from app.core.config import settings
from app.core.database import init_db
from app.api.v1.translations import router as translations_v1_router
from app.api.v1.audit import router as audit_v1_router

from app.services.observability import ObservabilityService
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

# CORS origins - centralized configuration
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3009",
    "http://localhost:3060",
    "http://localhost:8078",
    "http://localhost:8079",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3009",
    "http://127.0.0.1:3060",
    "http://127.0.0.1:8078",
    "http://127.0.0.1:8079",
]

# Allow Railway-deployed frontend origins via env var
_extra_origins = os.getenv("CORS_ORIGINS", "")
if _extra_origins:
    CORS_ORIGINS.extend([o.strip() for o in _extra_origins.split(",") if o.strip()])


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = ObservabilityService.start_timer()
        response = await call_next(request)
        duration = ObservabilityService.end_timer(start_time)

        # Track metric (simplified)
        ObservabilityService.track_request(duration_ms=duration)

        # Add header for debug
        response.headers["X-Processing-Time-Ms"] = str(duration)
        return response


class TenantContextMiddleware(BaseHTTPMiddleware):
    """TMX-3012 — set the tenant context for the duration of every request.

    Resolves `organization_id` from the authenticated user (when TMX-3013
    OIDC lands) or falls back to `DEFAULT_ORG_ID` for the single-tenant
    pilot. The fallback is THE last A3-adjacent transitional measure in
    the system; it lives at the request boundary, not in service code.

    Without this middleware, every API test against tenant-scoped tables
    would raise `TenantContextMissing` from the auto-filter listener.
    """

    async def dispatch(self, request: Request, call_next):
        from app.core.tenant_context import set_org_id, clear_org
        from app.models.database import DEFAULT_ORG_ID

        # TMX-3013 will resolve from IdP claims / session cookie. Until then
        # the pilot is single-tenant on DEFAULT_ORG_ID.
        org_id = DEFAULT_ORG_ID
        token = set_org_id(org_id)
        try:
            response = await call_next(request)
        finally:
            clear_org(token)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """TMX-LIFESPAN: startup/shutdown via the lifespan protocol (the deprecated
    @app.on_event handler is removed). Initialises the DB on boot; creates auth
    tables only when auth is enabled."""
    init_db()
    if getattr(settings, "auth_mode", "none") != "none":
        from app.models.auth import User  # noqa: F401 — registers model with Base
        from app.models.database import Base
        from app.core.database import engine

        Base.metadata.create_all(bind=engine)
    yield
    # No shutdown work today.


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
    lifespan=lifespan,
)

# IMPORTANT: Middleware order matters! They are processed in REVERSE order.
# CORS must be added LAST so it wraps everything (processed FIRST).

# Tenant-context middleware (TMX-3012). Inner-most so request handlers see
# the context but it's torn down before CORS/Observability finalises.
app.add_middleware(TenantContextMiddleware)

# Add observability middleware (processed after CORS)
app.add_middleware(ObservabilityMiddleware)

# CORS middleware - MUST be added LAST to be the outermost wrapper
# This ensures CORS headers are added to ALL responses including errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Processing-Time-Ms"],
)


# Global exception handler to ensure CORS headers on error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Ensure all exceptions return proper CORS headers."""
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in CORS_ORIGINS:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers=headers,
    )


# Auth router (always mounted; endpoints self-gate based on AUTH_MODE)
app.include_router(auth_router)

# Legacy translation router
app.include_router(api_router, prefix=settings.api_prefix)

# Platform v2.0 routers
app.include_router(documents_router)
app.include_router(segments_router)

# TMX-010: Prime Time API v1
app.include_router(
    translations_v1_router, prefix="/api/v1/translations", tags=["translations"]
)
app.include_router(audit_v1_router, prefix="/api/v1/audit", tags=["audit"])

# Translation Toolkit (Tools)
from app.api.tools import router as tools_router  # noqa: E402  (router import beside its registration)

app.include_router(tools_router, prefix="/api/tools", tags=["tools"])

# Knowledge / Trust Center
from app.api.knowledge import router as knowledge_router  # noqa: E402  (router import beside its registration)

app.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])

# TMX-FEEDBACK-1: in-app user feedback intake (prefix declared on the router)
from app.api.feedback import router as feedback_router  # noqa: E402  (router import beside its registration)

app.include_router(feedback_router)

# Dashboard Stats
from app.api.dashboard import router as dashboard_router  # noqa: E402  (router import beside its registration)

app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])

# Projects (TMX-PROJECTS) — job grouping for the workspace.
from app.api.projects import router as projects_router  # noqa: E402  (router import beside its registration)

app.include_router(projects_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "TransMax Pharma Translation", "version": "2.0"}
