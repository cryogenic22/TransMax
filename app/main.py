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

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
)

# IMPORTANT: Middleware order matters! They are processed in REVERSE order.
# CORS must be added LAST so it wraps everything (processed FIRST).

# Add observability middleware first (processed after CORS)
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
app.include_router(translations_v1_router, prefix="/api/v1/translations", tags=["translations"])
app.include_router(audit_v1_router, prefix="/api/v1/audit", tags=["audit"])

# Translation Toolkit (Tools)
from app.api.tools import router as tools_router
app.include_router(tools_router, prefix="/api/tools", tags=["tools"])

# Knowledge / Trust Center
from app.api.knowledge import router as knowledge_router
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])

# Dashboard Stats
from app.api.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()
    # Create auth tables only when auth is enabled (not in no-auth mode)
    if getattr(settings, "auth_mode", "none") != "none":
        from app.models.auth import User  # noqa: F401 — registers model with Base
        from app.models.database import Base
        from app.core.database import engine
        Base.metadata.create_all(bind=engine)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "TransMax Pharma Translation", "version": "2.0"}

