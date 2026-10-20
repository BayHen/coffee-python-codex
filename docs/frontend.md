# Frontend Architecture (Task 8)

## Kiến trúc

Frontend là một Vite SPA dùng React, TypeScript, Tailwind CSS v4 và React Router. Mỗi page gọi API qua `src/lib/api.ts`; không chứa giá hoặc tổng tiền tự quyết định thay backend.

```text
src/
├─ auth/AuthContext.tsx       access/refresh token trong memory, RBAC cho UI
├─ components/
│  ├─ AppLayout.tsx           sidebar, mobile navigation, user session
│  └─ ui.tsx                  button, field, panel, loading, error, empty state
├─ lib/api.ts                 fetch client, API errors, refresh-once, idempotency
├─ pages/
│  ├─ LoginPage.tsx
│  ├─ DashboardPage.tsx
│  ├─ ProductsPage.tsx        category/product/variant management
│  ├─ PosPage.tsx             cart và create order
│  ├─ OrdersPage.tsx          list, place, pay, cancel
│  └─ InventoryPage.tsx       stock, low-stock và manual movements
├─ test/                      Vitest + Testing Library workflows
├─ App.tsx                    route tree và protected layout
└─ types.ts                   types bám theo Pydantic responses
```

## Route structure

| Route | Chức năng | Quyền UI |
|---|---|---|
| `/login` | Đăng nhập | Public |
| `/` | Tổng quan API | Mọi role |
| `/products` | Danh mục, sản phẩm, biến thể | Đọc: mọi role; ghi: Admin/Manager |
| `/pos` | Chọn variant và tạo order draft | Mọi role |
| `/orders` | Xem, đặt, thanh toán, hủy đơn | Mọi role; hủy: Admin/Manager |
| `/inventory` | Tồn, cảnh báo, ledger | Đọc: mọi role; ghi: Admin/Manager |

Ẩn nút theo role chỉ cải thiện trải nghiệm. FastAPI vẫn kiểm tra JWT, session đang hoạt động và role ở mọi protected request.

## Authentication và API client

- Token pair chỉ nằm trong memory của `AuthProvider`, không ghi vào Local Storage hoặc Session Storage. Reload tab yêu cầu đăng nhập lại.
- Client thêm Bearer token cho request, thử refresh đúng một lần khi nhận 401, rồi xóa session nếu refresh thất bại.
- 403 được hiển thị như lỗi quyền từ backend, không tự đăng xuất.
- Request tạo order, payment và inventory movement sinh `Idempotency-Key` bằng `crypto.randomUUID()`.
- `VITE_API_BASE_URL` mặc định là `/api`. Vite dev server proxy đường dẫn này sang `http://127.0.0.1:8000`.

Trong production, reverse proxy `/api` về FastAPI cùng origin hoặc đặt `VITE_API_BASE_URL` thành URL gateway đã cấu hình CORS phù hợp.

## Chạy trên Windows

Hướng dẫn kết nối đầy đủ giữa PostgreSQL, FastAPI và React nằm tại
[database-connection.md](database-connection.md).

Terminal 1, từ repository root. Thay URL bằng database development thật của bạn:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
$env:JWT_SECRET_KEY = '<development-secret>'
npm.cmd run dev:api
```

`dev:api` cũng đọc `.env` cục bộ. File `.env` bị Git bỏ qua và không được dùng
làm file mẫu hoặc tài liệu.

Terminal 2, chạy trực tiếp từ repository root:

```powershell
npm.cmd --prefix frontend install
npm.cmd run dev
```

Root `package.json` chuyển tiếp `dev`, `build`, `lint` và `test` sang project trong
`frontend/`. Nếu terminal đang ở `frontend/`, có thể gọi trực tiếp `npm.cmd run dev`.

Mở `http://localhost:5173`. Không đặt JWT secret hoặc database credential trong file frontend. `VITE_*` luôn là cấu hình public được đóng gói vào browser bundle.

### Nếu login báo backend không phản hồi

Kiểm tra API trước:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
Invoke-WebRequest http://localhost:5173/api/health -UseBasicParsing
```

Cả hai request phải trả HTTP 200. Nếu terminal backend chưa có `DATABASE_URL` hoặc
`JWT_SECRET_KEY`, login không thể tạo database session hoặc JWT. Biến môi trường đặt ở
Terminal 1 không tự xuất hiện trong một terminal khác.

## Kiểm tra

```powershell
cd frontend
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd audit
```

Các test trọng tâm hiện có:

1. Đăng nhập thành công, điều hướng vào dashboard và không persist token.
2. Sai thông tin đăng nhập hiển thị lỗi backend.
3. POS tạo payload chỉ gồm variant/quantity và không gửi `unit_price` hoặc `total_amount`.

## Phạm vi

Customer và Employee backend đã có nhưng chưa có navigation UI trong Task 8 vì acceptance tập trung Product, POS và Inventory. Recipe editor cũng chưa được đưa vào màn hình; Inventory hiện cung cấp stock, low-stock và manual movements. Các endpoint vẫn được giữ nguyên để mở rộng ở task sau khi có yêu cầu.
