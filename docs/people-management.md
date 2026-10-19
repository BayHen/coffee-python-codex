# Customer & Employee Management (Task 7)

## Phạm vi và quan hệ dữ liệu

Module `people` quản lý hồ sơ khách hàng, nhân viên và sổ cái điểm thưởng. MVP không lưu địa chỉ, ngày sinh hoặc giấy tờ định danh vì nghiệp vụ chưa dùng các dữ liệu đó.

```mermaid
erDiagram
    ROLES ||--o{ USERS : "phân quyền"
    USERS ||--o| EMPLOYEES : "có thể liên kết"
    EMPLOYEES ||--o{ ORDERS : "tiếp nhận"
    CUSTOMERS ||--o{ ORDERS : "mua hàng"
    CUSTOMERS ||--o{ LOYALTY_TRANSACTIONS : "có sổ cái"
    ORDERS ||--o{ LOYALTY_TRANSACTIONS : "phát sinh earn/refund"
    USERS ||--o{ LOYALTY_TRANSACTIONS : "thực hiện điều chỉnh"
```

- `Employee.user_id` nullable và unique: nhân viên chỉ liên kết `User` khi cần đăng nhập; một tài khoản không thể đại diện hai nhân viên.
- `Order.customer_id` và `Order.employee_id` giữ quan hệ lịch sử. Vô hiệu hóa dùng `is_active`, không xóa dòng.
- Điểm hiện tại là `SUM(loyalty_transactions.points_delta)`, tránh một cột số dư có thể lệch khỏi lịch sử.
- Unique index có điều kiện bảo đảm mỗi order chỉ có tối đa một dòng `earn` và một dòng `refund`. `idempotency_key` unique cùng fingerprint ngăn retry tạo thêm giao dịch hoặc đổi payload.
- Email khách hàng và mã nhân viên có unique index không phân biệt hoa thường.

Trước khi migrate database có dữ liệu, kiểm tra email khách hàng hoặc mã nhân viên trùng nhau khi chuyển sang chữ thường. Migration không tự sửa dữ liệu nghiệp vụ và `downgrade` bị chặn vì sẽ xóa audit ledger.

## Quy tắc nghiệp vụ

- Một đơn `paid` có khách hàng nhận `floor(total_amount / 10.00)` điểm. Tổng tiền là `Decimal/Numeric` do server tính.
- Thanh toán retry cùng `Idempotency-Key` trả payment cũ; unique constraint theo order tiếp tục ngăn cộng điểm lần hai.
- Hoàn điểm tạo một dòng âm bằng đúng điểm đã nhận. Chỉ Admin/Manager thực hiện, chỉ một lần mỗi order, và số dư không được âm.
- Điều chỉnh thủ công cần lý do, `Idempotency-Key`, quyền Admin/Manager và không được làm số dư âm.
- Vô hiệu hóa Employee liên kết sẽ vô hiệu hóa User và thu hồi refresh session. Access token cũ không qua dependency. Kích hoạt lại Employee không tự kích hoạt User; Admin phải chủ động mở User qua API auth hiện có.
- Manager chỉ liên kết và quản lý Employee gắn tài khoản Staff. Admin quản lý mọi vai trò. Không ai được tự vô hiệu hóa chính mình qua Employee API.

## API và quyền

| Method | Endpoint | Staff | Manager/Admin |
|---|---|---:|---:|
| GET/POST | `/customers` | Có | Có |
| GET/PATCH | `/customers/{id}` | Có; Staff không đổi trạng thái | Có |
| DELETE | `/customers/{id}` | Không | Soft disable |
| GET | `/customers/{id}/orders` | Có | Có |
| GET | `/customers/{id}/loyalty` | Có | Có |
| POST | `/customers/{id}/loyalty-adjustments` | Không | Có |
| POST | `/orders/{id}/loyalty-refund` | Không | Có |
| GET | `/employees`, `/employees/{id}` | Có | Có |
| POST/PATCH/DELETE | `/employees...` | Không | Có, theo phạm vi vai trò |

List API nhận `search`, `is_active`, `page` và `page_size` (1–100). Customer search theo tên, phone, email; Employee search theo tên và mã. Response Employee không có email, password hash, token hoặc session. Lịch sử đơn khách hàng chỉ trả metadata và tổng tiền, không trả chi tiết item.

## JSON mẫu

```http
POST /customers
Authorization: Bearer <access-token>
Content-Type: application/json

{"full_name":"Nguyen An","phone":"+84912345678","email":"an@example.com"}
```

Tạo nhân viên và liên kết tài khoản đã có:

```json
{"employee_code":"STAFF-001","full_name":"Tran Binh","user_id":12,"is_active":true}
```

Điều chỉnh điểm với header `Idempotency-Key: loyalty-adjust-20261019-001`:

```json
{"points_delta":5,"reason":"Service recovery"}
```

Hoàn điểm order, dùng một idempotency key ổn định riêng cho sự kiện:

```json
{"reason":"Payment refunded"}
```

Lỗi nghiệp vụ chuẩn hóa:

```json
{"detail":{"code":"insufficient_loyalty_points","message":"Loyalty balance cannot become negative"}}
```

## Postman / Bruno

1. Tạo environment `baseUrl=http://127.0.0.1:8000`, `accessToken`, `customerId`, `employeeId`.
2. Gọi `POST {{baseUrl}}/auth/login`, lưu `access_token` vào `accessToken`.
3. Đặt header chung `Authorization: Bearer {{accessToken}}` và `Content-Type: application/json`.
4. Với create order, payment và loyalty write, thêm `Idempotency-Key`. Retry giữ nguyên key và body; nghiệp vụ mới dùng key mới.
5. Chạy create customer, tạo và thanh toán order, GET customer, GET loyalty, adjustment/refund rồi retry cùng key để xác minh không cộng/trừ hai lần.
6. Dùng token Staff gọi Employee write để thấy `403`; vô hiệu hóa Employee liên kết rồi dùng token cũ để thấy `401`.

## Migration và kiểm thử

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
.\.venv\Scripts\python.exe -m alembic upgrade head

$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev_test'
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Database test phải dùng database riêng có tên kết thúc bằng `_test` và đã migrate tới head. Fixture bọc mỗi test trong transaction rollback.
