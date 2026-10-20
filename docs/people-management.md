# Customer & Employee Management (Task 7)

## Pháº¡m vi vÃ  quan há»‡ dá»¯ liá»‡u

Module `people` quáº£n lÃ½ há»“ sÆ¡ khÃ¡ch hÃ ng, nhÃ¢n viÃªn vÃ  sá»• cÃ¡i Ä‘iá»ƒm thÆ°á»Ÿng. MVP khÃ´ng lÆ°u Ä‘á»‹a chá»‰, ngÃ y sinh hoáº·c giáº¥y tá» Ä‘á»‹nh danh vÃ¬ nghiá»‡p vá»¥ chÆ°a dÃ¹ng cÃ¡c dá»¯ liá»‡u Ä‘Ã³.

```mermaid
erDiagram
    ROLES ||--o{ USERS : "phÃ¢n quyá»n"
    USERS ||--o| EMPLOYEES : "cÃ³ thá»ƒ liÃªn káº¿t"
    EMPLOYEES ||--o{ ORDERS : "tiáº¿p nháº­n"
    CUSTOMERS ||--o{ ORDERS : "mua hÃ ng"
    CUSTOMERS ||--o{ LOYALTY_TRANSACTIONS : "cÃ³ sá»• cÃ¡i"
    ORDERS ||--o{ LOYALTY_TRANSACTIONS : "phÃ¡t sinh earn/refund"
    USERS ||--o{ LOYALTY_TRANSACTIONS : "thá»±c hiá»‡n Ä‘iá»u chá»‰nh"
```

- `Employee.user_id` nullable vÃ  unique: nhÃ¢n viÃªn chá»‰ liÃªn káº¿t `User` khi cáº§n Ä‘Äƒng nháº­p; má»™t tÃ i khoáº£n khÃ´ng thá»ƒ Ä‘áº¡i diá»‡n hai nhÃ¢n viÃªn.
- `Order.customer_id` vÃ  `Order.employee_id` giá»¯ quan há»‡ lá»‹ch sá»­. VÃ´ hiá»‡u hÃ³a dÃ¹ng `is_active`, khÃ´ng xÃ³a dÃ²ng.
- Äiá»ƒm hiá»‡n táº¡i lÃ  `SUM(loyalty_transactions.points_delta)`, trÃ¡nh má»™t cá»™t sá»‘ dÆ° cÃ³ thá»ƒ lá»‡ch khá»i lá»‹ch sá»­.
- Unique index cÃ³ Ä‘iá»u kiá»‡n báº£o Ä‘áº£m má»—i order chá»‰ cÃ³ tá»‘i Ä‘a má»™t dÃ²ng `earn` vÃ  má»™t dÃ²ng `refund`. `idempotency_key` unique cÃ¹ng fingerprint ngÄƒn retry táº¡o thÃªm giao dá»‹ch hoáº·c Ä‘á»•i payload.
- Email khÃ¡ch hÃ ng vÃ  mÃ£ nhÃ¢n viÃªn cÃ³ unique index khÃ´ng phÃ¢n biá»‡t hoa thÆ°á»ng.

TrÆ°á»›c khi migrate database cÃ³ dá»¯ liá»‡u, kiá»ƒm tra email khÃ¡ch hÃ ng hoáº·c mÃ£ nhÃ¢n viÃªn trÃ¹ng nhau khi chuyá»ƒn sang chá»¯ thÆ°á»ng. Migration khÃ´ng tá»± sá»­a dá»¯ liá»‡u nghiá»‡p vá»¥ vÃ  `downgrade` bá»‹ cháº·n vÃ¬ sáº½ xÃ³a audit ledger.

## Quy táº¯c nghiá»‡p vá»¥

- Má»™t Ä‘Æ¡n `paid` cÃ³ khÃ¡ch hÃ ng nháº­n `floor(total_amount / 10.00)` Ä‘iá»ƒm. Tá»•ng tiá»n lÃ  `Decimal/Numeric` do server tÃ­nh.
- Thanh toÃ¡n retry cÃ¹ng `Idempotency-Key` tráº£ payment cÅ©; unique constraint theo order tiáº¿p tá»¥c ngÄƒn cá»™ng Ä‘iá»ƒm láº§n hai.
- HoÃ n Ä‘iá»ƒm táº¡o má»™t dÃ²ng Ã¢m báº±ng Ä‘Ãºng Ä‘iá»ƒm Ä‘Ã£ nháº­n. Chá»‰ Admin/Manager thá»±c hiá»‡n, chá»‰ má»™t láº§n má»—i order, vÃ  sá»‘ dÆ° khÃ´ng Ä‘Æ°á»£c Ã¢m.
- Äiá»u chá»‰nh thá»§ cÃ´ng cáº§n lÃ½ do, `Idempotency-Key`, quyá»n Admin/Manager vÃ  khÃ´ng Ä‘Æ°á»£c lÃ m sá»‘ dÆ° Ã¢m.
- VÃ´ hiá»‡u hÃ³a Employee liÃªn káº¿t sáº½ vÃ´ hiá»‡u hÃ³a User vÃ  thu há»“i refresh session. Access token cÅ© khÃ´ng qua dependency. KÃ­ch hoáº¡t láº¡i Employee khÃ´ng tá»± kÃ­ch hoáº¡t User; Admin pháº£i chá»§ Ä‘á»™ng má»Ÿ User qua API auth hiá»‡n cÃ³.
- Manager chá»‰ liÃªn káº¿t vÃ  quáº£n lÃ½ Employee gáº¯n tÃ i khoáº£n Staff. Admin quáº£n lÃ½ má»i vai trÃ². KhÃ´ng ai Ä‘Æ°á»£c tá»± vÃ´ hiá»‡u hÃ³a chÃ­nh mÃ¬nh qua Employee API.

## API vÃ  quyá»n

| Method | Endpoint | Staff | Manager/Admin |
|---|---|---:|---:|
| GET/POST | `/customers` | CÃ³ | CÃ³ |
| GET/PATCH | `/customers/{id}` | CÃ³; Staff khÃ´ng Ä‘á»•i tráº¡ng thÃ¡i | CÃ³ |
| DELETE | `/customers/{id}` | KhÃ´ng | Soft disable |
| GET | `/customers/{id}/orders` | CÃ³ | CÃ³ |
| GET | `/customers/{id}/loyalty` | CÃ³ | CÃ³ |
| POST | `/customers/{id}/loyalty-adjustments` | KhÃ´ng | CÃ³ |
| POST | `/orders/{id}/loyalty-refund` | KhÃ´ng | CÃ³ |
| GET | `/employees`, `/employees/{id}` | CÃ³ | CÃ³ |
| POST/PATCH/DELETE | `/employees...` | KhÃ´ng | CÃ³, theo pháº¡m vi vai trÃ² |

List API nháº­n `search`, `is_active`, `page` vÃ  `page_size` (1â€“100). Customer search theo tÃªn, phone, email; Employee search theo tÃªn vÃ  mÃ£. Response Employee khÃ´ng cÃ³ email, password hash, token hoáº·c session. Lá»‹ch sá»­ Ä‘Æ¡n khÃ¡ch hÃ ng chá»‰ tráº£ metadata vÃ  tá»•ng tiá»n, khÃ´ng tráº£ chi tiáº¿t item.

## JSON máº«u

```http
POST /customers
Authorization: Bearer <access-token>
Content-Type: application/json

{"full_name":"Nguyen An","phone":"+84912345678","email":"an@example.com"}
```

Táº¡o nhÃ¢n viÃªn vÃ  liÃªn káº¿t tÃ i khoáº£n Ä‘Ã£ cÃ³:

```json
{"employee_code":"STAFF-001","full_name":"Tran Binh","user_id":12,"is_active":true}
```

Äiá»u chá»‰nh Ä‘iá»ƒm vá»›i header `Idempotency-Key: loyalty-adjust-20261019-001`:

```json
{"points_delta":5,"reason":"Service recovery"}
```

HoÃ n Ä‘iá»ƒm order, dÃ¹ng má»™t idempotency key á»•n Ä‘á»‹nh riÃªng cho sá»± kiá»‡n:

```json
{"reason":"Payment refunded"}
```

Lá»—i nghiá»‡p vá»¥ chuáº©n hÃ³a:

```json
{"detail":{"code":"insufficient_loyalty_points","message":"Loyalty balance cannot become negative"}}
```

## Postman / Bruno

1. Táº¡o environment `baseUrl=http://127.0.0.1:8000`, `accessToken`, `customerId`, `employeeId`.
2. Gá»i `POST {{baseUrl}}/auth/login`, lÆ°u `access_token` vÃ o `accessToken`.
3. Äáº·t header chung `Authorization: Bearer {{accessToken}}` vÃ  `Content-Type: application/json`.
4. Vá»›i create order, payment vÃ  loyalty write, thÃªm `Idempotency-Key`. Retry giá»¯ nguyÃªn key vÃ  body; nghiá»‡p vá»¥ má»›i dÃ¹ng key má»›i.
5. Cháº¡y create customer, táº¡o vÃ  thanh toÃ¡n order, GET customer, GET loyalty, adjustment/refund rá»“i retry cÃ¹ng key Ä‘á»ƒ xÃ¡c minh khÃ´ng cá»™ng/trá»« hai láº§n.
6. DÃ¹ng token Staff gá»i Employee write Ä‘á»ƒ tháº¥y `403`; vÃ´ hiá»‡u hÃ³a Employee liÃªn káº¿t rá»“i dÃ¹ng token cÅ© Ä‘á»ƒ tháº¥y `401`.

## Migration vÃ  kiá»ƒm thá»­

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
.\.venv\Scripts\python.exe -m alembic upgrade head

$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev_test'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Database test pháº£i dÃ¹ng database riÃªng cÃ³ tÃªn káº¿t thÃºc báº±ng `_test` vÃ  Ä‘Ã£ migrate tá»›i head. Fixture bá»c má»—i test trong transaction rollback.
