# Task 4 â€” Product and category management

## Thiáº¿t káº¿

Module `app.catalog` dÃ¹ng luá»“ng Router â†’ Service â†’ Repository. Router xá»­ lÃ½ HTTP vÃ 
RBAC; service giá»¯ transaction cÃ¹ng quy táº¯c nghiá»‡p vá»¥; repository chá»©a cÃ¢u truy váº¥n
SQLAlchemy. ÄÃ¢y lÃ  cÃ¡c lá»›p cá»¥ thá»ƒ cho catalog, khÃ´ng cÃ³ base repository hay interface
chÆ°a cáº§n thiáº¿t.

Admin vÃ  Manager Ä‘Æ°á»£c táº¡o, sá»­a, xÃ³a; Staff Ä‘Æ°á»£c Ä‘á»c. Má»i endpoint Ä‘á»u yÃªu cáº§u access
token há»£p lá»‡. `DELETE /products/{id}` vÃ  `DELETE` biáº¿n thá»ƒ chá»‰ Ä‘áº·t `is_active=false`,
vÃ¬ váº­y khÃ³a ngoáº¡i cá»§a `order_items` cÃ¹ng lá»‹ch sá»­ giÃ¡ bÃ¡n khÃ´ng bá»‹ máº¥t. Danh má»¥c rá»—ng
Ä‘Æ°á»£c xÃ³a trá»±c tiáº¿p. Danh má»¥c cÃ³ sáº£n pháº©m pháº£i chuyá»ƒn sáº£n pháº©m sang má»™t danh má»¥c
khÃ¡c trong cÃ¹ng transaction trÆ°á»›c khi xÃ³a.

GiÃ¡ dÃ¹ng JSON decimal vÃ  Ä‘Æ°á»£c lÆ°u báº±ng `NUMERIC(12,2)`. SKU Ä‘Æ°á»£c trim, viáº¿t hoa vÃ  chá»‰
cháº¥p nháº­n chá»¯ cÃ¡i Latin, sá»‘, dáº¥u `.`, `_`, `-`. TÃªn Ä‘Æ°á»£c trim vÃ  gá»™p khoáº£ng tráº¯ng.
Unique index má»›i kiá»ƒm tra khÃ´ng phÃ¢n biá»‡t hoa thÆ°á»ng.

## API

| Method | Path | Roles | MÃ´ táº£ |
| --- | --- | --- | --- |
| GET/POST | `/categories` | Read: all; write: Admin, Manager | Danh sÃ¡ch/táº¡o danh má»¥c |
| GET/PATCH/DELETE | `/categories/{id}` | Read: all; write: Admin, Manager | Chi tiáº¿t/sá»­a/xÃ³a rá»—ng |
| GET | `/categories/{id}/deletion-options` | Admin, Manager | Sá»‘ sáº£n pháº©m, danh má»¥c thay tháº¿ vÃ  gá»£i Ã½ TrÃ  |
| POST | `/categories/{id}/reassign-and-delete` | Admin, Manager | Chuyá»ƒn sáº£n pháº©m báº±ng ID rá»“i xÃ³a trong má»™t transaction |
| GET/POST | `/products` | Read: all; write: Admin, Manager | Danh sÃ¡ch/táº¡o sáº£n pháº©m |
| GET/PATCH/DELETE | `/products/{id}` | Read: all; write: Admin, Manager | Chi tiáº¿t/sá»­a/ngá»«ng bÃ¡n |
| GET/POST | `/products/{id}/variants` | Read: all; write: Admin, Manager | Danh sÃ¡ch/táº¡o size |
| GET/PATCH/DELETE | `/products/{id}/variants/{variant_id}` | Read: all; write: Admin, Manager | Chi tiáº¿t/sá»­a/ngá»«ng bÃ¡n size |

`GET /products` nháº­n `search`, `category_id`, `is_active`, `min_price`, `max_price`,
`sort_by=id|name`, `sort_direction=asc|desc`, `page`, `page_size`. Search khá»›p tÃªn
sáº£n pháº©m, tÃªn biáº¿n thá»ƒ hoáº·c SKU. `GET /categories` nháº­n search, sort vÃ  pagination.

VÃ­ dá»¥ táº¡o sáº£n pháº©m vÃ  size:

```json
{"category_id": 1, "name": "Latte", "is_active": true}
```

```json
{"sku": "LATTE-M", "name": "Size M", "price": "45000.00", "is_active": true}
```

Response lá»—i nghiá»‡p vá»¥ cÃ³ dáº¡ng:

```json
{"detail": {"code": "category_in_use", "message": "Category with products cannot be deleted"}}
```

Request xÃ¡c nháº­n chuyá»ƒn vÃ  xÃ³a:

```json
{"replacement_category_id": 2}
```

ID danh má»¥c thay tháº¿ do Admin xÃ¡c nháº­n; backend khÃ´ng hardcode ID vÃ  khÃ´ng tá»± táº¡o
danh má»¥c `TrÃ `. Endpoint xem trÆ°á»›c chá»‰ gá»£i Ã½ khi tÃ¬m tháº¥y Ä‘Ãºng má»™t tÃªn `TrÃ `
chuáº©n hÃ³a, khÃ´ng gá»£i Ã½ chÃ­nh danh má»¥c Ä‘ang xÃ³a.

Lá»—i validation cá»§a FastAPI tráº£ HTTP 422; thiáº¿u/sai token tráº£ 401; Ä‘Ãºng token nhÆ°ng
thiáº¿u vai trÃ² tráº£ 403.

## Migration vÃ  kiá»ƒm thá»­

Äá»c revision `c7d2f9a1b3e4` trÆ°á»›c khi cháº¡y. Náº¿u dá»¯ liá»‡u cÅ© cÃ³ giÃ¡ trá»‹ chá»‰ khÃ¡c hoa
thÆ°á»ng, unique index sáº½ tá»« chá»‘i migration Ä‘á»ƒ dá»¯ liá»‡u Ä‘Æ°á»£c xá»­ lÃ½ cÃ³ chá»§ Ä‘Ã­ch.

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
.\.venv\Scripts\python.exe -m alembic upgrade head

$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev_test'
.\.venv\Scripts\python.exe -m pytest
```
