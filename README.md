# Smart Coffee Shop Management System

Task 1 khởi tạo FastAPI; Task 2 thiết kế PostgreSQL; Task 3 bổ sung xác thực và phân quyền MVP. Frontend React và API nghiệp vụ chưa được triển khai.

## Yêu cầu

- Python 3.11+ (đã thử trên Python 3.14.3)
- Git
- PostgreSQL 18 (hoặc phiên bản tương thích để chạy migration)
- PowerShell trên Windows cho các lệnh bên dưới

## Cài đặt trên Windows

Chạy từ thư mục gốc repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Không cần kích hoạt virtual environment: gọi trực tiếp Python trong `.venv` tránh vấn đề PowerShell execution policy.

## Chạy API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Mở `http://127.0.0.1:8000/health` để xem `{"status":"ok"}` và `http://127.0.0.1:8000/docs` để xem tài liệu API. Dừng server bằng `Ctrl+C`.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
```

## PostgreSQL và migration (Task 2)

Tạo **database development riêng** nếu chưa có, ví dụ:

```powershell
createdb -h localhost -U postgres coffee_shop_dev
```

Đặt URL trong phiên PowerShell hiện tại; thay `USER`, `PASSWORD` bằng tài khoản của bạn. Nếu mật khẩu có ký tự đặc biệt, URL-encode phần mật khẩu. Không ghi URL thật vào Git.

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

Trước `upgrade head` trên database có dữ liệu, kiểm tra `DATABASE_URL`, backup và đọc file revision trong `backend/alembic/versions/`. Migration đầu tiên chỉ tạo bảng, index và constraint; không xóa bảng hiện có. Không chạy `downgrade` trên database có dữ liệu.

Để chạy test ràng buộc PostgreSQL, tạo thêm database **riêng** có tên kết thúc `_test` và chạy migration ở database đó:

```powershell
createdb -h localhost -U postgres coffee_shop_dev_test
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev_test'
.\.venv\Scripts\python.exe -m alembic upgrade head
$env:TEST_DATABASE_URL = $env:DATABASE_URL
.\.venv\Scripts\python.exe -m pytest
```

Test PostgreSQL rollback dữ liệu sau mỗi bài test; thiếu `TEST_DATABASE_URL` thì các bài test này được skip. Xem [docs/database-design.md](docs/database-design.md) để biết ERD, khóa, chuẩn hóa và protocol transaction. `/health` vẫn chỉ kiểm tra tiến trình API, chưa truy vấn database.

## Xác thực và phân quyền (Task 3)

Sau `alembic upgrade head`, tạo JWT secret ngẫu nhiên trong environment và khởi tạo Admin đầu tiên qua terminal:

```powershell
$env:JWT_SECRET_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
.\.venv\Scripts\python.exe -m app.auth.bootstrap_admin --email admin@example.com
```

Giữ secret này ổn định và an toàn; không commit vào repository. Xem [docs/authentication.md](docs/authentication.md) để biết API login, refresh, logout, quyền Admin/Manager/Staff, ví dụ Postman/Bruno và cách xử lý 401/403. Bài test auth dùng database `_test` đã migrate và tự tạo JWT secret thử nghiệm.

## Cấu trúc

```text
backend/app/       FastAPI application
backend/app/auth/  login, phiên và phân quyền
backend/app/db/    SQLAlchemy models và session
backend/tests/     Pytest tests
backend/alembic/   Alembic migration
frontend/          vị trí cho React ở task sau
docs/              tài liệu kiến trúc
.github/workflows/ CI cho backend
```

Xem [docs/architecture.md](docs/architecture.md) để biết hướng phát triển modular monolith và [AGENTS.md](AGENTS.md) để biết quy tắc làm việc với Codex.

## Product & Category Management (Task 4)

Sau khi chạy migration mới nhất, các endpoint `/categories`, `/products` và
`/products/{id}/variants` xuất hiện trong `/docs`. Admin và Manager có quyền ghi;
Staff có quyền đọc. Xem [docs/catalog-api.md](docs/catalog-api.md) để biết query
filter, JSON mẫu, chính sách soft delete và cách kiểm thử.

## Order Management (Task 5)

Các endpoint `/orders` hỗ trợ tạo draft, snapshot giá/tên, discount, state machine,
lịch sử sự kiện và thanh toán mô phỏng có idempotency. Xem
[docs/order-management.md](docs/order-management.md) để biết state diagram, JSON mẫu,
quy tắc transaction và kiểm thử concurrency.

## Inventory Management (Task 6)

Module inventory quản lý nguyên liệu, recipe, ledger nhập/xuất/điều chỉnh, cảnh báo
tồn thấp và tự động tiêu thụ khi order được placed. Hủy order placed tạo các dòng hoàn
kho tương ứng. Xem [docs/inventory-management.md](docs/inventory-management.md) để biết
quy ước đơn vị, API và thứ tự locking.

## Customer & Employee Management (Task 7)

Module `people` cung cấp Customer/Employee CRUD, lịch sử mua hàng và loyalty ledger có
idempotency. Vô hiệu hóa giữ nguyên lịch sử; nhân viên liên kết với User bị vô hiệu hóa sẽ
bị thu hồi phiên đăng nhập. Xem [docs/people-management.md](docs/people-management.md)
để biết quan hệ dữ liệu, ma trận quyền, API và hướng dẫn Postman/Bruno.

## Frontend Development (Task 8)

Frontend React + TypeScript nằm trong `frontend/`, gồm login, responsive dashboard,
Product Management, POS/Orders và Inventory. Chạy `npm.cmd --prefix frontend install`
rồi `npm.cmd run dev` tại repository root; Vite proxy `/api` về FastAPI cục bộ. Xem
[docs/frontend.md](docs/frontend.md) để biết route, component tree, RBAC và testing.
Backend phải chạy riêng bằng `npm.cmd run dev:api` trong terminal đã có `DATABASE_URL`
và `JWT_SECRET_KEY`.
Xem [docs/database-connection.md](docs/database-connection.md) để khởi động database,
backend và frontend theo đúng thứ tự.

## Cấu hình cục bộ

`.env.example` là mẫu cấu hình. Nếu cần, sao chép thành `.env` và thay placeholder trên máy cá nhân. Lệnh `npm.cmd run dev:api` nạp `.env` cho môi trường development; các cách chạy backend khác cần nhận `DATABASE_URL` và `JWT_SECRET_KEY` từ process. `.env` đã nằm trong `.gitignore`.

## Git và GitHub

Repository đã có Git và remote `origin`. Kiểm tra địa chỉ trước khi dùng:

```powershell
git status
git remote -v
git add README.md AGENTS.md .gitignore .env.example pyproject.toml alembic.ini backend frontend docs .github
git commit -m "Initialize Smart Coffee Shop project"
```

Nếu clone hoặc khởi tạo repository khác và chưa có remote, tạo repository trống trên GitHub rồi chạy `git remote add origin https://github.com/<user>/<repo>.git`. Khi muốn chia sẻ, tự kiểm tra thay đổi và chạy `git push -u origin main`. Không đưa `.env` hoặc secrets vào commit.

