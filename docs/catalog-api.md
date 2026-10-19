# Task 4 — Product and category management

## Thiết kế

Module `app.catalog` dùng luồng Router → Service → Repository. Router xử lý HTTP và
RBAC; service giữ transaction cùng quy tắc nghiệp vụ; repository chứa câu truy vấn
SQLAlchemy. Đây là các lớp cụ thể cho catalog, không có base repository hay interface
chưa cần thiết.

Admin và Manager được tạo, sửa, xóa; Staff được đọc. Mọi endpoint đều yêu cầu access
token hợp lệ. `DELETE /products/{id}` và `DELETE` biến thể chỉ đặt `is_active=false`,
vì vậy khóa ngoại của `order_items` cùng lịch sử giá bán không bị mất. Danh mục chỉ
được xóa khi chưa có sản phẩm.

Giá dùng JSON decimal và được lưu bằng `NUMERIC(12,2)`. SKU được trim, viết hoa và chỉ
chấp nhận chữ cái Latin, số, dấu `.`, `_`, `-`. Tên được trim và gộp khoảng trắng.
Unique index mới kiểm tra không phân biệt hoa thường.

## API

| Method | Path | Roles | Mô tả |
| --- | --- | --- | --- |
| GET/POST | `/categories` | Read: all; write: Admin, Manager | Danh sách/tạo danh mục |
| GET/PATCH/DELETE | `/categories/{id}` | Read: all; write: Admin, Manager | Chi tiết/sửa/xóa rỗng |
| GET/POST | `/products` | Read: all; write: Admin, Manager | Danh sách/tạo sản phẩm |
| GET/PATCH/DELETE | `/products/{id}` | Read: all; write: Admin, Manager | Chi tiết/sửa/ngừng bán |
| GET/POST | `/products/{id}/variants` | Read: all; write: Admin, Manager | Danh sách/tạo size |
| GET/PATCH/DELETE | `/products/{id}/variants/{variant_id}` | Read: all; write: Admin, Manager | Chi tiết/sửa/ngừng bán size |

`GET /products` nhận `search`, `category_id`, `is_active`, `min_price`, `max_price`,
`sort_by=id|name`, `sort_direction=asc|desc`, `page`, `page_size`. Search khớp tên
sản phẩm, tên biến thể hoặc SKU. `GET /categories` nhận search, sort và pagination.

Ví dụ tạo sản phẩm và size:

```json
{"category_id": 1, "name": "Latte", "is_active": true}
```

```json
{"sku": "LATTE-M", "name": "Size M", "price": "45000.00", "is_active": true}
```

Response lỗi nghiệp vụ có dạng:

```json
{"detail": {"code": "category_in_use", "message": "Category with products cannot be deleted"}}
```

Lỗi validation của FastAPI trả HTTP 422; thiếu/sai token trả 401; đúng token nhưng
thiếu vai trò trả 403.

## Migration và kiểm thử

Đọc revision `c7d2f9a1b3e4` trước khi chạy. Nếu dữ liệu cũ có giá trị chỉ khác hoa
thường, unique index sẽ từ chối migration để dữ liệu được xử lý có chủ đích.

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
.\.venv\Scripts\python.exe -m alembic upgrade head

$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev_test'
.\.venv\Scripts\python.exe -m pytest
```
