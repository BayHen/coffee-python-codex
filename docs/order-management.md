# Task 5 — Order Management

## State machine

```mermaid
stateDiagram-v2
    [*] --> draft: create order
    draft --> draft: replace items / discount
    draft --> placed: confirm order
    draft --> cancelled: Manager/Admin cancels
    placed --> paid: simulated payment succeeds
    placed --> placed: simulated payment fails
    placed --> cancelled: Manager/Admin cancels
    paid --> [*]
    cancelled --> [*]
```

`paid` và `cancelled` là trạng thái cuối. Staff có thể tạo, sửa draft, xác nhận và
thanh toán; chỉ Manager/Admin có thể hủy. Mỗi lần tạo, sửa, đổi trạng thái hoặc thử
thanh toán đều ghi `order_events`.

## API

| Method | Path | Mô tả |
| --- | --- | --- |
| POST | `/orders` | Tạo draft; bắt buộc header `Idempotency-Key` |
| GET | `/orders` | Danh sách, lọc `status`, pagination |
| GET | `/orders/{id}` | Chi tiết gồm items, events, payments |
| PUT | `/orders/{id}` | Thay toàn bộ items/discount khi còn draft |
| POST | `/orders/{id}/transitions` | Chuyển sang `placed` hoặc `cancelled` |
| POST | `/orders/{id}/payments` | Thanh toán mô phỏng; bắt buộc idempotency key |

Ví dụ tạo đơn:

```http
POST /orders
Authorization: Bearer <access-token>
Idempotency-Key: pos-terminal-01-000001
Content-Type: application/json
```

```json
{
  "customer_id": null,
  "items": [
    {"variant_id": 10, "quantity": 2},
    {"variant_id": 12, "quantity": 1}
  ],
  "discount_percent": "10.00",
  "discount_reason": "Opening promotion"
}
```

Client không được gửi tên, giá, subtotal, discount amount hoặc total. Request có
field thừa bị trả 422. Server khóa variant, kiểm tra product và variant còn bán, rồi
chụp `product_name`, `variant_name`, `sku`, `unit_price` và `line_total`.

Ví dụ response rút gọn:

```json
{
  "id": 42,
  "status": "draft",
  "subtotal_amount": "11.45",
  "discount_percent": "10.00",
  "discount_amount": "1.15",
  "total_amount": "10.30",
  "items": [
    {
      "variant_id": 10,
      "product_name": "Latte",
      "variant_name": "Size M",
      "sku": "LATTE-M",
      "quantity": 2,
      "unit_price": "4.55",
      "line_total": "9.10"
    }
  ]
}
```

Thanh toán mô phỏng:

```http
POST /orders/42/payments
Idempotency-Key: payment-terminal-01-000001
```

```json
{"method": "card_demo", "outcome": "succeeded"}
```

`method` chỉ nhận `cash` hoặc `card_demo`; `outcome` cho phép test `succeeded` và
`failed`. API không kết nối cổng thanh toán và không xử lý tiền thật.

## Tiền, discount và transaction

- Tất cả số tiền dùng `Decimal`/`NUMERIC`, làm tròn `ROUND_HALF_UP` đến 2 chữ số.
- Discount là phần trăm từ 0 đến 20. Discount dương bắt buộc có lý do.
- `subtotal = SUM(unit_price × quantity)`.
- `discount_amount = round(subtotal × discount_percent / 100, 2)`.
- `total = subtotal - discount_amount`.
- Subtotal phải dương. Database kiểm tra thành phần tổng, line total và giới hạn discount.

Tạo đơn chạy trong một `session.begin()`: kiểm tra idempotency, khóa các variant theo
thứ tự ID, chụp giá/tên, tính tổng, ghi order/items/event rồi commit cùng lúc. Việc
khóa cả product và variant ngăn cập nhật menu chen giữa lúc kiểm tra trạng thái và
chụp giá.

Thanh toán khóa dòng order bằng `SELECT FOR UPDATE`. Hai request đồng thời vì vậy
được tuần tự hóa; request thứ hai thấy order đã `paid` và bị từ chối. Unique key trên
`payments.idempotency_key` chống replay, còn partial unique index trên một payment
`succeeded` mỗi order là lớp bảo vệ cuối ở database. Retry cùng key và cùng payload
trả lại bản ghi cũ; dùng lại key với payload khác trả 409.

Task này không ghi `inventory_transactions` và không trừ nguyên liệu.

## Lỗi thường gặp

- Gửi giá hoặc total từ POS: 422 vì request cấm field thừa.
- Dùng một variant hai lần: 422; tăng `quantity` trên một dòng.
- Discount trên 20% hoặc thiếu lý do: 422.
- Product/variant đã ngừng bán: 409 `variant_unavailable`.
- Sửa đơn sau khi placed: 409 `order_not_editable`.
- Chuyển trạng thái sai: 409 `invalid_order_transition`.
- Thanh toán draft/paid/cancelled: 409 `order_not_payable`.
- Dùng lại idempotency key cho payload khác: 409 `idempotency_key_reused`.
- Staff hủy đơn: 403.

## Chạy migration và test

Đọc revision `e5a8c2d4f6b7` trước khi áp dụng. Migration backfill snapshot và totals
cho dữ liệu cũ; downgrade bị chặn vì cần kế hoạch bảo toàn lịch sử.

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
.\.venv\Scripts\python.exe -m alembic upgrade head

$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev_test'
.\.venv\Scripts\python.exe -m pytest
```

Test concurrency tạo dữ liệu có suffix ngẫu nhiên trong database `_test`, chạy hai
payment bằng hai connection thật, xác nhận chỉ một payment thành công, rồi xóa đúng
các bản ghi test đã tạo.

## Checklist

- [x] Server lấy giá hiện tại và tự tính tổng.
- [x] Snapshot tên, SKU, giá và line total.
- [x] Decimal, discount validation và database constraints.
- [x] State machine và event history.
- [x] Soft history độc lập với thay đổi menu.
- [x] Idempotency cho create order và payment.
- [x] Row lock cùng unique constraints chống double payment.
- [x] Không trừ kho trong Task 5.

## Câu hỏi kiến thức

1. Vì sao unique idempotency key vẫn cần request fingerprint?
2. `SELECT FOR UPDATE` bảo vệ double payment khác gì partial unique index?
3. Vì sao `OrderItem` phải lưu snapshot thay vì luôn join giá hiện tại?
4. Điều gì xảy ra nếu tính tiền bằng `float` và làm tròn ở cuối?
5. Vì sao event và thay đổi trạng thái phải commit trong cùng transaction?
