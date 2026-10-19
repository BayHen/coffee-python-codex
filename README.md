# Smart Coffee Shop Management System

Task 1 khởi tạo backend FastAPI; Task 2 thiết kế PostgreSQL schema và migration. Frontend React và API nghiệp vụ chưa được triển khai.

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

## Cấu trúc

```text
backend/app/       FastAPI application
backend/tests/     Pytest tests
backend/alembic/   Alembic migration
frontend/          vị trí cho React ở task sau
docs/              tài liệu kiến trúc
.github/workflows/ CI cho backend
```

Xem [docs/architecture.md](docs/architecture.md) để biết hướng phát triển modular monolith và [AGENTS.md](AGENTS.md) để biết quy tắc làm việc với Codex.

## Cấu hình cục bộ

`.env.example` là mẫu cấu hình. Nếu cần, sao chép thành `.env` và thay placeholder trên máy cá nhân. Ứng dụng **không tự tải** file `.env`; hãy đưa `DATABASE_URL` vào môi trường process trước khi dùng database hoặc Alembic. `.env` đã nằm trong `.gitignore`.

## Git và GitHub

Repository đã có Git và remote `origin`. Kiểm tra địa chỉ trước khi dùng:

```powershell
git status
git remote -v
git add README.md AGENTS.md .gitignore .env.example pyproject.toml alembic.ini backend frontend docs .github
git commit -m "Initialize Smart Coffee Shop project"
```

Nếu clone hoặc khởi tạo repository khác và chưa có remote, tạo repository trống trên GitHub rồi chạy `git remote add origin https://github.com/<user>/<repo>.git`. Khi muốn chia sẻ, tự kiểm tra thay đổi và chạy `git push -u origin main`. Không đưa `.env` hoặc secrets vào commit.

