# Kết nối PostgreSQL, FastAPI và React

## Cấu hình development hiện tại

```text
React/Vite       http://localhost:5173
       │ /api proxy
       ▼
FastAPI          http://127.0.0.1:8000
       │ DATABASE_URL từ .env
       ▼
PostgreSQL       127.0.0.1:55433
Database         coffee_shop_dev
User             coffee_dev
```

`.env` là file cục bộ bị Git bỏ qua. `.env.example` chỉ chứa placeholder và không được
điền credential thật.

## Khởi động hằng ngày

Mở ba terminal tại repository root.

Terminal 1, database:

```powershell
npm.cmd run dev:db
```

Terminal 2, backend:

```powershell
npm.cmd run dev:api
```

`dev:api` đọc `DATABASE_URL` và `JWT_SECRET_KEY` từ `.env`, sau đó chạy FastAPI ở cổng
8000.

Terminal 3, frontend:

```powershell
npm.cmd run dev
```

Vite đọc [vite.config.ts](../frontend/vite.config.ts) và chuyển `/api/*` sang backend.
Frontend không được kết nối PostgreSQL trực tiếp.

## Kiểm tra từng lớp

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\pg_isready.exe' -h 127.0.0.1 -p 55433
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
Invoke-WebRequest http://localhost:5173/api/health -UseBasicParsing
```

Kết quả mong đợi:

```text
127.0.0.1:55433 - accepting connections
HTTP 200 {"status":"ok"}
HTTP 200 {"status":"ok"}
```

## Migration

`alembic` không tự đọc `.env` khi gọi trực tiếp. Nạp biến vào terminal trước:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}

.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Không chạy `downgrade` hoặc drop database có dữ liệu cần giữ.

## Tài khoản Admin development

```text
Email: ngobayhen.tdc2019@gmail.com
Role:  Admin
```

Mật khẩu không được ghi trong tài liệu hoặc commit. Nếu cần tạo lại Admin sau một lần
reset database:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}

.\.venv\Scripts\python.exe -m app.auth.bootstrap_admin --email ngobayhen.tdc2019@gmail.com
```

## Lỗi thường gặp

- `connection timeout`: PostgreSQL chưa chạy hoặc sai port. Chạy `npm.cmd run dev:db`.
- `password authentication failed`: URL đang trỏ nhầm PostgreSQL service ở cổng 5432 hoặc credential sai.
- `/api/health` trả 500/502: backend chưa chạy ở cổng 8000.
- `/api/health` trả 404: Vite được chạy sai working directory hoặc sai config. Chạy từ root bằng `npm.cmd run dev`.
- Login trả 401: email hoặc mật khẩu sai.
- Login trả 403: User hoặc Employee liên kết đã bị vô hiệu hóa.
