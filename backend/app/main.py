"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="Smart Coffee Shop API")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is responding."""
    return {"status": "ok"}
