"""Revenue reporting endpoints restricted to management roles."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, require_roles
from app.db.session import get_session
from app.reporting.schemas import (
    DailyRevenueReport,
    RevenueSummary,
    TopProductsReport,
)
from app.reporting.service import DEFAULT_TIMEZONE, ReportingService, resolve_period

router = APIRouter(prefix="/reports", tags=["reports"])
Manager = Annotated[Principal, Depends(require_roles("Admin", "Manager"))]
Db = Annotated[Session, Depends(get_session)]


@router.get("/revenue/summary", response_model=RevenueSummary)
def revenue_summary(
    _principal: Manager,
    db: Db,
    date_from: date | None = None,
    date_to: date | None = None,
    timezone: Annotated[str, Query(min_length=1, max_length=64)] = DEFAULT_TIMEZONE,
) -> RevenueSummary:
    period = resolve_period(date_from, date_to, timezone)
    return ReportingService(db).summary(period)


@router.get("/revenue/daily", response_model=DailyRevenueReport)
def daily_revenue(
    _principal: Manager,
    db: Db,
    date_from: date | None = None,
    date_to: date | None = None,
    timezone: Annotated[str, Query(min_length=1, max_length=64)] = DEFAULT_TIMEZONE,
) -> DailyRevenueReport:
    period = resolve_period(date_from, date_to, timezone)
    return ReportingService(db).daily(period)


@router.get("/top-products", response_model=TopProductsReport)
def top_products(
    _principal: Manager,
    db: Db,
    date_from: date | None = None,
    date_to: date | None = None,
    timezone: Annotated[str, Query(min_length=1, max_length=64)] = DEFAULT_TIMEZONE,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> TopProductsReport:
    period = resolve_period(date_from, date_to, timezone)
    return ReportingService(db).top_products(period, limit)
