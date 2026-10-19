# Task 6 — Inventory Management

## Mô hình dữ liệu

```mermaid
erDiagram
    INGREDIENTS ||--o{ RECIPES : used_by
    PRODUCT_VARIANTS ||--o{ RECIPES : requires
    INGREDIENTS ||--o{ INVENTORY_TRANSACTIONS : ledger
    ORDER_ITEMS |o--o{ INVENTORY_TRANSACTIONS : consumes_or_returns
    USERS |o--o{ INVENTORY_TRANSACTIONS : records
    INVENTORY_TRANSACTIONS |o--o| INVENTORY_TRANSACTIONS : reverses
```

- `Ingredients` lưu SKU, tên, đơn vị chuẩn, ngưỡng cảnh báo và trạng thái active.
- `Recipes` lưu lượng nguyên liệu cần cho một `ProductVariant`.
- `InventoryTransactions` là ledger append only. Tồn kho được tính bằng
  `SUM(quantity_delta)`, không có cột số dư thứ hai để bị lệch dữ liệu.
- `reversal_of_id` nối transaction hoàn kho với sale gốc và có unique constraint.

Đơn vị MVP chỉ gồm `g`, `ml`, `piece`. API không tự quy đổi `kg → g` hoặc `l → ml`.
Mỗi nguyên liệu dùng đúng một đơn vị cơ sở; không được đổi đơn vị sau khi đã có recipe
hoặc lịch sử kho.

## Thời điểm trừ và hoàn kho

```mermaid
flowchart LR
    A[Create draft] -->|No stock change| B[Draft]
    B -->|Place order| C[Lock order and recipes]
    C --> D[Lock ingredients by ID]
    D --> E{Enough stock?}
    E -->|No| F[Rollback, order stays draft]
    E -->|Yes| G[Append sale transactions]
    G --> H[Order becomes placed]
    H -->|Payment| I[Paid, no stock change]
    H -->|Cancel| J[Append return transactions]
    J --> K[Cancelled]
```

- Tạo hoặc sửa draft không thay đổi tồn.
- `draft → placed`: đọc recipe hiện tại, khóa variant và ingredient theo ID, kiểm tra
  tổng ledger, ghi `sale` âm và đổi trạng thái trong cùng transaction.
- `placed → cancelled`: hoàn chính xác từng sale bằng transaction `return` dương.
- Payment không thay đổi kho.
- `paid` không được hủy trong workflow hiện tại.
- Order cũ đã placed trước Task 6 nhưng không có sale ledger sẽ không được tự động
  cộng kho khi hủy.

## API

| Method | Endpoint | Quyền | Mô tả |
| --- | --- | --- | --- |
| GET/POST | `/ingredients` | Read: all; write: Admin/Manager | Danh sách/tạo nguyên liệu |
| GET/PATCH/DELETE | `/ingredients/{id}` | Read: all; write: Admin/Manager | Xem/sửa/ngừng dùng |
| GET | `/ingredients/low-stock` | All | Nguyên liệu active có tồn `<=` ngưỡng |
| GET | `/product-variants/{variant_id}/recipes` | All | Công thức variant |
| PUT/DELETE | `/product-variants/{variant_id}/recipes/{ingredient_id}` | Admin/Manager | Upsert/xóa định mức |
| GET | `/inventory/transactions` | All | Ledger có filter và pagination |
| POST | `/inventory/transactions` | Admin/Manager | Nhập, xuất hao hụt, điều chỉnh |

Ví dụ tạo nguyên liệu:

```json
{
  "sku": "MILK-FRESH",
  "name": "Fresh Milk",
  "unit": "ml",
  "low_stock_threshold": "5000.000"
}
```

Ví dụ recipe:

```json
{"quantity_required": "250.000"}
```

Ví dụ nhập kho:

```http
POST /inventory/transactions
Idempotency-Key: receiving-20261019-0001
```

```json
{
  "ingredient_id": 1,
  "transaction_type": "purchase",
  "quantity_delta": "10000.000",
  "reason": "Supplier delivery INV-001"
}
```

Manual movement dùng quy ước:

- `purchase`: delta dương.
- `waste`: delta âm.
- `adjustment`: delta dương hoặc âm nhưng không được bằng 0.
- Mọi movement bắt buộc có reason và `Idempotency-Key`.
- `sale` và `return` chỉ do order workflow tạo, client không được gửi trực tiếp.

## Transaction, locking và chống tồn âm

Mọi code thay đổi số lượng đều khóa dòng `ingredients` bằng `SELECT FOR UPDATE` trước
khi tính `SUM(quantity_delta)`. Nhiều nguyên liệu luôn được khóa theo `ingredient.id`
để giảm deadlock. Sau khi có lock, service kiểm tra `current + delta >= 0` rồi mới append
ledger row.

Khi đặt đơn, variant được khóa trước ingredient. Recipe API cũng khóa theo thứ tự đó,
vì vậy recipe không thể thay đổi giữa lúc order đọc định mức và ghi sale. Order status,
sale/return transactions và event history cùng commit hoặc cùng rollback.

Idempotency được bảo vệ bằng key unique và request fingerprint. Sale key được tạo ổn
định từ order item + ingredient; return key từ order + sale ID. Partial unique index cũ
vẫn ngăn hai sale cho cùng order item và ingredient; unique `reversal_of_id` ngăn hoàn
một sale hai lần.

## Migration

Revision `f6b9d3e5a7c8`:

- Thêm threshold và soft status cho ingredient.
- Chuẩn hóa unit bằng check constraint.
- Thêm actor, reason, fingerprint và reversal link cho ledger.
- Mở rộng transaction type với `return`.
- Không sửa bất kỳ `quantity_delta` cũ nào.
- Backfill metadata cho transaction cũ.

Migration sẽ dừng nếu dữ liệu cũ dùng unit ngoài `g`, `ml`, `piece`, hoặc có SKU/tên
trùng nhau khi so sánh không phân biệt hoa thường. Cần rà soát dữ liệu và quyết định
mapping thủ công; migration không tự quy đổi hay gộp tồn.

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Checklist

- [x] Ingredient CRUD với soft delete.
- [x] Đơn vị cơ sở thống nhất.
- [x] Recipe theo ProductVariant.
- [x] Nhập, waste và adjustment có reason/RBAC/idempotency.
- [x] Ledger chỉ append, không có API sửa/xóa.
- [x] Tồn tính từ tổng ledger.
- [x] Low-stock endpoint.
- [x] Trừ kho ở `placed`, hoàn ở cancellation.
- [x] Row lock và thứ tự lock ổn định.
- [x] Chặn tồn âm.
- [x] Test API, order integration và cạnh tranh hai connection.
