"""Revenue definitions, timezone boundaries, and report assembly."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.reporting.repository import ReportingRepository
from app.reporting.schemas import (
    DailyRevenuePoint,
    DailyRevenueReport,
    RevenueSummary,
    TopProduct,
    TopProductsReport,
)

CENT = Decimal("0.01")
DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"
MAX_REPORT_DAYS = 366


@dataclass(frozen=True)
class ReportPeriod:
    date_from: date
    date_to: date
    timezone_name: str
    start_utc: datetime
    end_utc: datetime


def report_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code, detail={"code": code, "message": message}
    )


def resolve_period(
    date_from: date | None,
    date_to: date | None,
    timezone_name: str,
    *,
    now: datetime | None = None,
) -> ReportPeriod:
    try:
        local_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise report_error(422, "invalid_timezone", "Unknown IANA timezone") from exc
    current = now or datetime.now(UTC)
    local_today = current.astimezone(local_timezone).date()
    end_date = date_to or local_today
    start_date = date_from or (end_date - timedelta(days=29))
    if start_date > end_date:
        raise report_error(
            422, "invalid_date_range", "date_from must not exceed date_to"
        )
    if (end_date - start_date).days + 1 > MAX_REPORT_DAYS:
        raise report_error(
            422, "date_range_too_large", "Date range cannot exceed 366 days"
        )
    start_local = datetime.combine(start_date, time.min, tzinfo=local_timezone)
    end_local = datetime.combine(
        end_date + timedelta(days=1), time.min, tzinfo=local_timezone
    )
    return ReportPeriod(
        date_from=start_date,
        date_to=end_date,
        timezone_name=timezone_name,
        start_utc=start_local.astimezone(UTC),
        end_utc=end_local.astimezone(UTC),
    )


class ReportingService:
    def __init__(self, db: Session) -> None:
        self.repository = ReportingRepository(db)

    def summary(self, period: ReportPeriod) -> RevenueSummary:
        revenue, order_count, cash_revenue, bank_revenue, session_count = (
            self.repository.revenue_summary(period.start_utc, period.end_utc)
        )
        refunded_amount, refunded_count = self.repository.refunded_summary(
            period.start_utc, period.end_utc
        )
        average = (
            (revenue / order_count).quantize(CENT, rounding=ROUND_HALF_UP)
            if order_count
            else Decimal("0.00")
        )
        return RevenueSummary(
            date_from=period.date_from,
            date_to=period.date_to,
            timezone=period.timezone_name,
            total_revenue=revenue.quantize(CENT),
            valid_order_count=order_count,
            average_order_value=average,
            refunded_amount=refunded_amount.quantize(CENT),
            refunded_payment_count=refunded_count,
            cash_revenue=cash_revenue.quantize(CENT),
            bank_transfer_revenue=bank_revenue.quantize(CENT),
            paid_session_count=session_count,
            revenue_by_method={
                "cash": cash_revenue.quantize(CENT),
                "bank_transfer": bank_revenue.quantize(CENT),
            },
        )

    def daily(self, period: ReportPeriod) -> DailyRevenueReport:
        rows = {
            row_date: (revenue.quantize(CENT), order_count)
            for row_date, revenue, order_count in self.repository.daily_revenue(
                period.start_utc, period.end_utc, period.timezone_name
            )
        }
        items = []
        current_date = period.date_from
        while current_date <= period.date_to:
            revenue, order_count = rows.get(current_date, (Decimal("0.00"), 0))
            items.append(
                DailyRevenuePoint(
                    date=current_date,
                    revenue=revenue,
                    order_count=order_count,
                )
            )
            current_date += timedelta(days=1)
        return DailyRevenueReport(
            date_from=period.date_from,
            date_to=period.date_to,
            timezone=period.timezone_name,
            items=items,
        )

    def top_products(self, period: ReportPeriod, limit: int) -> TopProductsReport:
        rows = self.repository.top_products(period.start_utc, period.end_utc, limit)
        items = [
            TopProduct(
                product_name=product_name,
                variant_name=variant_name,
                sku=sku,
                quantity_sold=quantity_sold,
                gross_item_sales=gross_item_sales.quantize(CENT),
            )
            for product_name, variant_name, sku, quantity_sold, gross_item_sales in rows
        ]
        return TopProductsReport(
            date_from=period.date_from,
            date_to=period.date_to,
            timezone=period.timezone_name,
            items=items,
        )
