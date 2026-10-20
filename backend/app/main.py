"""FastAPI application entry point and HTTP security policy."""

import os
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.ai.router import router as ai_router
from app.auth.router import router as auth_router
from app.catalog.router import router as catalog_router
from app.inventory.router import router as inventory_router
from app.orders.router import router as orders_router
from app.people.router import router as people_router
from app.reporting.router import router as reporting_router


def cors_origins() -> list[str]:
    origins = []
    for raw_origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(","):
        origin = raw_origin.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlsplit(origin)
        if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("CORS_ALLOWED_ORIGINS contains an invalid origin")
        origins.append(origin)
    return list(dict.fromkeys(origins))


app = FastAPI(title="Smart Coffee Shop API")
allowed_origins = cors_origins()
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
app.include_router(ai_router)
app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(people_router)
app.include_router(reporting_router)


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith(("/auth", "/ai", "/reports")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is responding."""
    return {"status": "ok"}
