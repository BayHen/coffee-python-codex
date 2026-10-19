# Authentication & Authorization (MVP)

## Chính sách

- Mật khẩu được hash bằng Argon2 (`pwdlib`); `users.password_hash` không chứa mật khẩu gốc. Không có API đăng ký công khai.
- Access token là JWT HS256, hạn 15 phút. Token chứa `sub` (user ID), `sid` (session ID), `type=access`, `iss`, `aud`, `iat`, `nbf`, `exp`, `jti`. JWT được ký bằng `JWT_SECRET_KEY` từ environment; key phải có ít nhất 32 byte. Server chỉ chấp nhận thuật toán HS256 cố định.
- Refresh token là chuỗi ngẫu nhiên 256 bit, hạn tuyệt đối 7 ngày kể từ login. `auth_sessions` chỉ lưu SHA-256 hash. Refresh khóa dòng phiên bằng `FOR UPDATE`, thay token hash và trả cặp token mới. Token cũ bị từ chối ngay.
- Logout đặt `revoked_at` cho phiên. Mỗi request có Bearer token kiểm tra chữ ký JWT **và** phiên trong PostgreSQL, nên cả access và refresh token của phiên bị từ chối ngay sau logout. Khóa tài khoản cũng thu hồi các phiên của tài khoản đó; mở khóa không khôi phục phiên cũ.
- Role lấy từ database trên mỗi request: thay đổi quyền có hiệu lực ngay. `Admin` quản lý tài khoản, `Manager` xem role, `Staff` chỉ dùng endpoint dành cho người dùng đã xác thực.
- Email được chuẩn hóa chữ thường khi tạo qua API/script; unique index trên `lower(users.email)` chặn tài khoản trùng chỉ khác chữ hoa/thường. Khi áp dụng migration lên DB đã có dữ liệu, xử lý các email trùng kiểu này trước.

Hệ thống chưa tích hợp rate limiting ở edge/proxy. Trước khi mở API ra Internet, cấu hình HTTPS và giới hạn tần suất login/refresh tại reverse proxy hoặc API gateway. Với React, giữ token trong bộ nhớ; không lưu access hoặc refresh token vào `localStorage`/`sessionStorage`. Nếu cần duy trì đăng nhập qua lần tải trang mới, triển khai cookie refresh `HttpOnly`, `Secure`, `SameSite` cùng kiểm soát CSRF trước khi dùng trên production. Xem [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

## Quyền truy cập

| Endpoint | Admin | Manager | Staff |
|---|---:|---:|---:|
| `GET /auth/me`, `POST /auth/logout` | Có | Có | Có |
| `GET /auth/roles` | Có | Có | 403 |
| `GET /auth/users`, `POST /auth/users`, `PATCH /auth/users/{id}/status` | Có | 403 | 403 |

`POST /auth/login` và `POST /auth/refresh` không cần access token. `POST /auth/users` là cách Admin tạo Manager/Staff và Admin bổ sung; chỉ trả thông tin tài khoản, không trả mật khẩu hoặc hash. Admin không thể tự khóa mình qua API này.

## HTTP 401 và 403

| Trường hợp | Status |
|---|---:|
| Sai email/mật khẩu | 401 |
| Thiếu Bearer token, token sai chữ ký, sai loại, hết hạn hoặc phiên đã thu hồi | 401 |
| Refresh token sai/hết hạn/đã xoay vòng | 401 |
| Mật khẩu đúng nhưng tài khoản đang bị vô hiệu hóa | 403 |
| Tài khoản hợp lệ nhưng role không đủ quyền | 403 |

Yêu cầu JSON sai cấu trúc hoặc email không hợp lệ trả 422. Tài khoản mới trùng email trả 409.

## Khởi tạo Admin đầu tiên trên Windows

Từ thư mục gốc, sau khi cài dependencies và chạy migration trên **database development riêng**:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
$env:JWT_SECRET_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.auth.bootstrap_admin --email admin@example.com
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Script yêu cầu terminal tương tác, hỏi mật khẩu hai lần và không in mật khẩu. Mật khẩu Admin cần tối thiểu 12 ký tự. Script tạo `Admin`, `Manager`, `Staff` nếu chưa có và từ chối tạo Admin bootstrap lần thứ hai. Lưu `JWT_SECRET_KEY` ổn định trong secret manager/environment của dịch vụ; thay key sẽ làm mọi access token hiện tại mất hiệu lực. File `.env` không được tự tải; nếu dùng file này cho máy cá nhân, phải nạp biến vào process theo cách riêng và không commit.

## API và ví dụ cho Postman/Bruno

Tạo environment `baseUrl=http://127.0.0.1:8000`. Đặt `Content-Type: application/json` cho các POST/PATCH. Thực hiện theo thứ tự:

1. **Login:** `POST {{baseUrl}}/auth/login` với body `{"email":"admin@example.com","password":"<your-password>"}`. Response 200:

   ```json
   {"access_token":"<jwt>","refresh_token":"<opaque-token>","token_type":"bearer","expires_in":900}
   ```

2. **Dùng quyền:** `GET {{baseUrl}}/auth/me` với header `Authorization: Bearer <jwt>`. Response chứa `id`, `email`, `role`, `is_active`. Trong Postman/Bruno có thể chọn Bearer Auth và dán `access_token`.
3. **Tạo Staff/Manager:** Admin gọi `POST {{baseUrl}}/auth/users` với Bearer token và body `{"email":"staff@example.com","password":"<new-strong-password>","role":"Staff"}`. Password tối thiểu 12 ký tự; response 201 không chứa password/hash.
4. **Refresh:** `POST {{baseUrl}}/auth/refresh` với body `{"refresh_token":"<opaque-token>"}`. Thay **cả hai** token trong environment bằng token mới; refresh token cũ trả 401.
5. **Khóa tài khoản:** Admin gọi `PATCH {{baseUrl}}/auth/users/<id>/status` với body `{"is_active":false}`. Tài khoản bị khóa không login được, phiên cũ bị thu hồi.
6. **Logout:** `POST {{baseUrl}}/auth/logout` với Bearer access token. Response 204; gọi lại `/auth/me` hoặc `/auth/refresh` bằng token phiên đó trả 401.

Các response token có `Cache-Control: no-store`. Không đưa token thật, mật khẩu hoặc JWT secret vào collection được commit. Có thể thử các endpoint và schema trong `/docs`.
