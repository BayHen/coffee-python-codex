# Smart Coffee Shop Management System

Task 1 khởi tạo backend FastAPI và cấu trúc repository. Frontend React và PostgreSQL chưa được triển khai.

## Yêu cầu

- Python 3.11+ (đã thử trên Python 3.14.3)
- Git
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

## Cấu trúc

```text
backend/app/       FastAPI application
backend/tests/     Pytest tests
frontend/          vị trí cho React ở task sau
docs/              tài liệu kiến trúc
.github/workflows/ CI cho backend
```

Xem [docs/architecture.md](docs/architecture.md) để biết hướng phát triển modular monolith và [AGENTS.md](AGENTS.md) để biết quy tắc làm việc với Codex.

## Cấu hình cục bộ

`.env.example` là mẫu cho các task sau. Nếu cần, sao chép thành `.env` và thay placeholder trên máy cá nhân. Ứng dụng hiện chưa đọc các biến này; `.env` đã nằm trong `.gitignore`.

## Git và GitHub

Repository đã có Git và remote `origin`. Kiểm tra địa chỉ trước khi dùng:

```powershell
git status
git remote -v
git add README.md AGENTS.md .gitignore .env.example pyproject.toml backend frontend docs .github
git commit -m "Initialize Smart Coffee Shop project"
```

Nếu clone hoặc khởi tạo repository khác và chưa có remote, tạo repository trống trên GitHub rồi chạy `git remote add origin https://github.com/<user>/<repo>.git`. Khi muốn chia sẻ, tự kiểm tra thay đổi và chạy `git push -u origin main`. Không đưa `.env` hoặc secrets vào commit.

