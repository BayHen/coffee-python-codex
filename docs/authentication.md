# Authentication & Authorization (MVP)

## ChÃ­nh sÃ¡ch

- Máº­t kháº©u Ä‘Æ°á»£c hash báº±ng Argon2 (`pwdlib`); `users.password_hash` khÃ´ng chá»©a máº­t kháº©u gá»‘c. KhÃ´ng cÃ³ API Ä‘Äƒng kÃ½ cÃ´ng khai.
- Access token lÃ  JWT HS256, háº¡n 15 phÃºt. Token chá»©a `sub` (user ID), `sid` (session ID), `type=access`, `iss`, `aud`, `iat`, `nbf`, `exp`, `jti`. JWT Ä‘Æ°á»£c kÃ½ báº±ng `JWT_SECRET_KEY` tá»« environment; key pháº£i cÃ³ Ã­t nháº¥t 32 byte. Server chá»‰ cháº¥p nháº­n thuáº­t toÃ¡n HS256 cá»‘ Ä‘á»‹nh.
- Refresh token lÃ  chuá»—i ngáº«u nhiÃªn 256 bit, háº¡n tuyá»‡t Ä‘á»‘i 7 ngÃ y ká»ƒ tá»« login. `auth_sessions` chá»‰ lÆ°u SHA-256 hash. Refresh khÃ³a dÃ²ng phiÃªn báº±ng `FOR UPDATE`, thay token hash vÃ  tráº£ cáº·p token má»›i. Token cÅ© bá»‹ tá»« chá»‘i ngay.
- Logout Ä‘áº·t `revoked_at` cho phiÃªn. Má»—i request cÃ³ Bearer token kiá»ƒm tra chá»¯ kÃ½ JWT **vÃ ** phiÃªn trong PostgreSQL, nÃªn cáº£ access vÃ  refresh token cá»§a phiÃªn bá»‹ tá»« chá»‘i ngay sau logout. KhÃ³a tÃ i khoáº£n cÅ©ng thu há»“i cÃ¡c phiÃªn cá»§a tÃ i khoáº£n Ä‘Ã³; má»Ÿ khÃ³a khÃ´ng khÃ´i phá»¥c phiÃªn cÅ©.
- Role láº¥y tá»« database trÃªn má»—i request: thay Ä‘á»•i quyá»n cÃ³ hiá»‡u lá»±c ngay. `Admin` quáº£n lÃ½ tÃ i khoáº£n, `Manager` xem role, `Staff` chá»‰ dÃ¹ng endpoint dÃ nh cho ngÆ°á»i dÃ¹ng Ä‘Ã£ xÃ¡c thá»±c.
- Email Ä‘Æ°á»£c chuáº©n hÃ³a chá»¯ thÆ°á»ng khi táº¡o qua API/script; unique index trÃªn `lower(users.email)` cháº·n tÃ i khoáº£n trÃ¹ng chá»‰ khÃ¡c chá»¯ hoa/thÆ°á»ng. Khi Ã¡p dá»¥ng migration lÃªn DB Ä‘Ã£ cÃ³ dá»¯ liá»‡u, xá»­ lÃ½ cÃ¡c email trÃ¹ng kiá»ƒu nÃ y trÆ°á»›c.

Há»‡ thá»‘ng chÆ°a tÃ­ch há»£p rate limiting á»Ÿ edge/proxy. TrÆ°á»›c khi má»Ÿ API ra Internet, cáº¥u hÃ¬nh HTTPS vÃ  giá»›i háº¡n táº§n suáº¥t login/refresh táº¡i reverse proxy hoáº·c API gateway. Vá»›i React, giá»¯ token trong bá»™ nhá»›; khÃ´ng lÆ°u access hoáº·c refresh token vÃ o `localStorage`/`sessionStorage`. Náº¿u cáº§n duy trÃ¬ Ä‘Äƒng nháº­p qua láº§n táº£i trang má»›i, triá»ƒn khai cookie refresh `HttpOnly`, `Secure`, `SameSite` cÃ¹ng kiá»ƒm soÃ¡t CSRF trÆ°á»›c khi dÃ¹ng trÃªn production. Xem [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

## Quyá»n truy cáº­p

| Endpoint | Admin | Manager | Staff |
|---|---:|---:|---:|
| `GET /auth/me`, `POST /auth/logout` | CÃ³ | CÃ³ | CÃ³ |
| `GET /auth/roles` | CÃ³ | CÃ³ | 403 |
| `GET /auth/users`, `POST /auth/users`, `PATCH /auth/users/{id}/status` | CÃ³ | 403 | 403 |

`POST /auth/login` vÃ  `POST /auth/refresh` khÃ´ng cáº§n access token. `POST /auth/users` lÃ  cÃ¡ch Admin táº¡o Manager/Staff vÃ  Admin bá»• sung; chá»‰ tráº£ thÃ´ng tin tÃ i khoáº£n, khÃ´ng tráº£ máº­t kháº©u hoáº·c hash. Admin khÃ´ng thá»ƒ tá»± khÃ³a mÃ¬nh qua API nÃ y.

## HTTP 401 vÃ  403

| TrÆ°á»ng há»£p | Status |
|---|---:|
| Sai email/máº­t kháº©u | 401 |
| Thiáº¿u Bearer token, token sai chá»¯ kÃ½, sai loáº¡i, háº¿t háº¡n hoáº·c phiÃªn Ä‘Ã£ thu há»“i | 401 |
| Refresh token sai/háº¿t háº¡n/Ä‘Ã£ xoay vÃ²ng | 401 |
| Máº­t kháº©u Ä‘Ãºng nhÆ°ng tÃ i khoáº£n Ä‘ang bá»‹ vÃ´ hiá»‡u hÃ³a | 403 |
| TÃ i khoáº£n há»£p lá»‡ nhÆ°ng role khÃ´ng Ä‘á»§ quyá»n | 403 |

YÃªu cáº§u JSON sai cáº¥u trÃºc hoáº·c email khÃ´ng há»£p lá»‡ tráº£ 422. TÃ i khoáº£n má»›i trÃ¹ng email tráº£ 409.

## Khá»Ÿi táº¡o Admin Ä‘áº§u tiÃªn trÃªn Windows

Tá»« thÆ° má»¥c gá»‘c, sau khi cÃ i dependencies vÃ  cháº¡y migration trÃªn **database development riÃªng**:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
$env:JWT_SECRET_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.auth.bootstrap_admin --email admin@example.com
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Script yÃªu cáº§u terminal tÆ°Æ¡ng tÃ¡c, há»i máº­t kháº©u hai láº§n vÃ  khÃ´ng in máº­t kháº©u. Máº­t kháº©u Admin cáº§n tá»‘i thiá»ƒu 12 kÃ½ tá»±. Script táº¡o `Admin`, `Manager`, `Staff` náº¿u chÆ°a cÃ³ vÃ  tá»« chá»‘i táº¡o Admin bootstrap láº§n thá»© hai. LÆ°u `JWT_SECRET_KEY` á»•n Ä‘á»‹nh trong secret manager/environment cá»§a dá»‹ch vá»¥; thay key sáº½ lÃ m má»i access token hiá»‡n táº¡i máº¥t hiá»‡u lá»±c. File `.env` khÃ´ng Ä‘Æ°á»£c tá»± táº£i; náº¿u dÃ¹ng file nÃ y cho mÃ¡y cÃ¡ nhÃ¢n, pháº£i náº¡p biáº¿n vÃ o process theo cÃ¡ch riÃªng vÃ  khÃ´ng commit.

## API vÃ  vÃ­ dá»¥ cho Postman/Bruno

Táº¡o environment `baseUrl=http://127.0.0.1:8000`. Äáº·t `Content-Type: application/json` cho cÃ¡c POST/PATCH. Thá»±c hiá»‡n theo thá»© tá»±:

1. **Login:** `POST {{baseUrl}}/auth/login` vá»›i body `{"email":"admin@example.com","password":"<your-password>"}`. Response 200:

   ```json
   {"access_token":"<jwt>","refresh_token":"<opaque-token>","token_type":"bearer","expires_in":900}
   ```

2. **DÃ¹ng quyá»n:** `GET {{baseUrl}}/auth/me` vá»›i header `Authorization: Bearer <jwt>`. Response chá»©a `id`, `email`, `role`, `is_active`. Trong Postman/Bruno cÃ³ thá»ƒ chá»n Bearer Auth vÃ  dÃ¡n `access_token`.
3. **Táº¡o Staff/Manager:** Admin gá»i `POST {{baseUrl}}/auth/users` vá»›i Bearer token vÃ  body `{"email":"staff@example.com","password":"<new-strong-password>","role":"Staff"}`. Password tá»‘i thiá»ƒu 12 kÃ½ tá»±; response 201 khÃ´ng chá»©a password/hash.
4. **Refresh:** `POST {{baseUrl}}/auth/refresh` vá»›i body `{"refresh_token":"<opaque-token>"}`. Thay **cáº£ hai** token trong environment báº±ng token má»›i; refresh token cÅ© tráº£ 401.
5. **KhÃ³a tÃ i khoáº£n:** Admin gá»i `PATCH {{baseUrl}}/auth/users/<id>/status` vá»›i body `{"is_active":false}`. TÃ i khoáº£n bá»‹ khÃ³a khÃ´ng login Ä‘Æ°á»£c, phiÃªn cÅ© bá»‹ thu há»“i.
6. **Logout:** `POST {{baseUrl}}/auth/logout` vá»›i Bearer access token. Response 204; gá»i láº¡i `/auth/me` hoáº·c `/auth/refresh` báº±ng token phiÃªn Ä‘Ã³ tráº£ 401.

CÃ¡c response token cÃ³ `Cache-Control: no-store`. KhÃ´ng Ä‘Æ°a token tháº­t, máº­t kháº©u hoáº·c JWT secret vÃ o collection Ä‘Æ°á»£c commit. CÃ³ thá»ƒ thá»­ cÃ¡c endpoint vÃ  schema trong `/docs`.
