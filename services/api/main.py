import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request as FastAPIRequest, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from packages.core.config import get_settings
from services.api.exceptions import AppException
from services.api.routes import auth, tenants

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s (req_id=%(request_id)s): %(message)s"
    if hasattr(logging, "LogRecord")
    else "%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("enterprise_rag.api")

app = FastAPI(
    title="Enterprise Multi-Tenant RAG & Document Intelligence Platform API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: FastAPIRequest, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestCorrelationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Contract-Compliant Error Envelope Handlers
@app.exception_handler(AppException)
async def app_exception_handler(request: FastAPIRequest, exc: AppException):
    request_id = getattr(request.state, "request_id", "req_unknown")
    logger.warning(f"AppException: code={exc.code} status={exc.status_code} msg={exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
                "details": exc.details,
            }
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: FastAPIRequest, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", "req_unknown")
    errors = exc.errors()
    simplified_details = {
        ".".join(str(loc) for loc in err["loc"] if loc != "body"): err["msg"]
        for err in errors
    }
    logger.info(f"Validation error: {simplified_details}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters or payload.",
                "request_id": request_id,
                "details": simplified_details,
            }
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: FastAPIRequest, exc: Exception):
    request_id = getattr(request.state, "request_id", "req_unknown")
    logger.exception(f"Unhandled server error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred. Please contact support.",
                "request_id": request_id,
                "details": {},
            }
        },
    )

# Health Checks
@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "enterprise-rag-api",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }

# Register Version 1 Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
