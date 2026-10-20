# Revenue reporting

## Business definition

- Revenue is the sum of `payments.amount` for payments whose status is `succeeded`.
- A cancelled order is excluded defensively, even if inconsistent legacy data contains a succeeded payment for it.
- Pending and failed payments and unpaid orders do not count as revenue.
- A payment with status `refunded` is excluded from revenue and shown separately as refunded amount. The current payment model supports full refunds; partial refunds need a separate refund ledger before they can be reported accurately.
- Valid order count is the distinct number of orders with a qualifying payment. Average order value is revenue divided by that count, rounded to two decimal places.
- Best sellers use snapshot fields in `order_items`, so later product edits do not rewrite history. `gross_item_sales` is item value before order-level discount.

Dates are inclusive calendar dates in the requested IANA timezone. The default is `Asia/Ho_Chi_Minh`. The backend converts local midnight boundaries to a half-open UTC interval (`created_at >= start` and `created_at < next_day`) so the payment timestamp index remains usable. A request may span at most 366 days.

## API

All endpoints require an Admin or Manager access token. An authenticated Staff user receives HTTP 403.

```http
GET /reports/revenue/summary?date_from=2026-10-01&date_to=2026-10-31&timezone=Asia%2FHo_Chi_Minh
GET /reports/revenue/daily?date_from=2026-10-01&date_to=2026-10-31&timezone=Asia%2FHo_Chi_Minh
GET /reports/top-products?date_from=2026-10-01&date_to=2026-10-31&timezone=Asia%2FHo_Chi_Minh&limit=10
Authorization: Bearer <access-token>
```

Example summary:

```json
{
  "date_from": "2026-10-01",
  "date_to": "2026-10-31",
  "timezone": "Asia/Ho_Chi_Minh",
  "total_revenue": "145.00",
  "valid_order_count": 2,
  "average_order_value": "72.50",
  "refunded_amount": "70.00",
  "refunded_payment_count": 1
}
```

Money is calculated with PostgreSQL `NUMERIC` and Python `Decimal` and serialized as decimal strings.

## SQL aggregation

Summary query, simplified:

```sql
SELECT COALESCE(SUM(p.amount), 0) AS total_revenue,
       COUNT(DISTINCT p.order_id) AS valid_order_count
FROM payments AS p
JOIN orders AS o ON o.id = p.order_id
WHERE p.status = 'succeeded'
  AND o.status <> 'cancelled'
  AND p.created_at >= :start_utc
  AND p.created_at < :end_utc;
```

Daily grouping converts timestamps only after the indexed UTC range filter:

```sql
SELECT CAST(timezone(:timezone, p.created_at) AS date) AS local_date,
       SUM(p.amount) AS revenue,
       COUNT(DISTINCT p.order_id) AS order_count
FROM payments AS p
JOIN orders AS o ON o.id = p.order_id
WHERE p.status = 'succeeded'
  AND o.status <> 'cancelled'
  AND p.created_at >= :start_utc
  AND p.created_at < :end_utc
GROUP BY local_date
ORDER BY local_date;
```

Migration `b9d1e3f5a7c2` adds `(status, created_at, order_id)` on `payments`. The leading status and timestamp columns serve the report filter; `order_id` supports the join and distinct count. Existing indexes on `order_items.order_id` support the best-seller join.

## Dashboard

Admin and Manager users see summary cards, an actual daily revenue bar chart, top products, and date controls. Staff users do not request report endpoints and see operational counts instead. The backend remains the permission authority.

## Verification

Backend integration tests seed succeeded, failed, refunded, and cancelled cases. They reconcile `145.00` revenue, two valid orders, zero-filled calendar days, and product ranking. Run:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://coffee_dev@127.0.0.1:55433/coffee_shop_test"
python -m alembic -c backend/alembic.ini upgrade head
python -m pytest
python -m ruff check .
python -m ruff format --check .
cd frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

## Review questions

1. Why does revenue use payment timestamps instead of order creation timestamps?
2. Why is the upper date boundary exclusive?
3. How does a composite index beginning with payment status help this query?
4. Why is best-seller value called gross item sales when orders can have discounts?
5. What schema change is needed to represent partial refunds correctly?
