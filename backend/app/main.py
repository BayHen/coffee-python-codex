"""FastAPI application entry point."""

from fastapi import FastAPI

from app.auth.router import router as auth_router

app = FastAPI(title="Smart Coffee Shop API")
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is responding."""
    return {"status": "ok"}
