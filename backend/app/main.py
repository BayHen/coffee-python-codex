"""FastAPI application entry point."""

from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.catalog.router import router as catalog_router
from app.inventory.router import router as inventory_router
from app.orders.router import router as orders_router

app = FastAPI(title="Smart Coffee Shop API")
app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(inventory_router)
app.include_router(orders_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is responding."""
    return {"status": "ok"}
