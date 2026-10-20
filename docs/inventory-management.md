# Task 6 â€” Inventory Management

## MÃ´ hÃ¬nh dá»¯ liá»‡u

```mermaid
erDiagram
    INGREDIENTS ||--o{ RECIPES : used_by
    PRODUCT_VARIANTS ||--o{ RECIPES : requires
    INGREDIENTS ||--o{ INVENTORY_TRANSACTIONS : ledger
    ORDER_ITEMS |o--o{ INVENTORY_TRANSACTIONS : consumes_or_returns
    USERS |o--o{ INVENTORY_TRANSACTIONS : records
    INVENTORY_TRANSACTIONS |o--o| INVENTORY_TRANSACTIONS : reverses
```

- `Ingredients` lÆ°u SKU, tÃªn, Ä‘Æ¡n vá»‹ chuáº©n, ngÆ°á»¡ng cáº£nh bÃ¡o vÃ  tráº¡ng thÃ¡i active.
- `Recipes` lÆ°u lÆ°á»£ng nguyÃªn liá»‡u cáº§n cho má»™t `ProductVariant`.
- `InventoryTransactions` lÃ  ledger append only. Tá»“n kho Ä‘Æ°á»£c tÃ­nh báº±ng
  `SUM(quantity_delta)`, khÃ´ng cÃ³ cá»™t sá»‘ dÆ° thá»© hai Ä‘á»ƒ bá»‹ lá»‡ch dá»¯ liá»‡u.
- `reversal_of_id` ná»‘i transaction hoÃ n kho vá»›i sale gá»‘c vÃ  cÃ³ unique constraint.

ÄÆ¡n vá»‹ MVP chá»‰ gá»“m `g`, `ml`, `piece`. API khÃ´ng tá»± quy Ä‘á»•i `kg â†’ g` hoáº·c `l â†’ ml`.
Má»—i nguyÃªn liá»‡u dÃ¹ng Ä‘Ãºng má»™t Ä‘Æ¡n vá»‹ cÆ¡ sá»Ÿ; khÃ´ng Ä‘Æ°á»£c Ä‘á»•i Ä‘Æ¡n vá»‹ sau khi Ä‘Ã£ cÃ³ recipe
hoáº·c lá»‹ch sá»­ kho.

## Thá»i Ä‘iá»ƒm trá»« vÃ  hoÃ n kho

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

- Táº¡o hoáº·c sá»­a draft khÃ´ng thay Ä‘á»•i tá»“n.
- `draft â†’ placed`: Ä‘á»c recipe hiá»‡n táº¡i, khÃ³a variant vÃ  ingredient theo ID, kiá»ƒm tra
  tá»•ng ledger, ghi `sale` Ã¢m vÃ  Ä‘á»•i tráº¡ng thÃ¡i trong cÃ¹ng transaction.
- `placed â†’ cancelled`: hoÃ n chÃ­nh xÃ¡c tá»«ng sale báº±ng transaction `return` dÆ°Æ¡ng.
- Payment khÃ´ng thay Ä‘á»•i kho.
- `paid` khÃ´ng Ä‘Æ°á»£c há»§y trong workflow hiá»‡n táº¡i.
- Order cÅ© Ä‘Ã£ placed trÆ°á»›c Task 6 nhÆ°ng khÃ´ng cÃ³ sale ledger sáº½ khÃ´ng Ä‘Æ°á»£c tá»± Ä‘á»™ng
  cá»™ng kho khi há»§y.

## API

| Method | Endpoint | Quyá»n | MÃ´ táº£ |
| --- | --- | --- | --- |
| GET/POST | `/ingredients` | Read: all; write: Admin/Manager | Danh sÃ¡ch/táº¡o nguyÃªn liá»‡u |
| GET/PATCH/DELETE | `/ingredients/{id}` | Read: all; write: Admin/Manager | Xem/sá»­a/ngá»«ng dÃ¹ng |
| GET | `/ingredients/low-stock` | All | NguyÃªn liá»‡u active cÃ³ tá»“n `<=` ngÆ°á»¡ng |
| GET | `/product-variants/{variant_id}/recipes` | All | CÃ´ng thá»©c variant |
| PUT/DELETE | `/product-variants/{variant_id}/recipes/{ingredient_id}` | Admin/Manager | Upsert/xÃ³a Ä‘á»‹nh má»©c |
| GET | `/inventory/transactions` | All | Ledger cÃ³ filter vÃ  pagination |
| POST | `/inventory/transactions` | Admin/Manager | Nháº­p, xuáº¥t hao há»¥t, Ä‘iá»u chá»‰nh |

VÃ­ dá»¥ táº¡o nguyÃªn liá»‡u:

```json
{
  "sku": "MILK-FRESH",
  "name": "Fresh Milk",
  "unit": "ml",
  "low_stock_threshold": "5000.000"
}
```

VÃ­ dá»¥ recipe:

```json
{"quantity_required": "250.000"}
```

VÃ­ dá»¥ nháº­p kho:

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

Manual movement dÃ¹ng quy Æ°á»›c:

- `purchase`: delta dÆ°Æ¡ng.
- `waste`: delta Ã¢m.
- `adjustment`: delta dÆ°Æ¡ng hoáº·c Ã¢m nhÆ°ng khÃ´ng Ä‘Æ°á»£c báº±ng 0.
- Má»i movement báº¯t buá»™c cÃ³ reason vÃ  `Idempotency-Key`.
- `sale` vÃ  `return` chá»‰ do order workflow táº¡o, client khÃ´ng Ä‘Æ°á»£c gá»­i trá»±c tiáº¿p.

## Transaction, locking vÃ  chá»‘ng tá»“n Ã¢m

Má»i code thay Ä‘á»•i sá»‘ lÆ°á»£ng Ä‘á»u khÃ³a dÃ²ng `ingredients` báº±ng `SELECT FOR UPDATE` trÆ°á»›c
khi tÃ­nh `SUM(quantity_delta)`. Nhiá»u nguyÃªn liá»‡u luÃ´n Ä‘Æ°á»£c khÃ³a theo `ingredient.id`
Ä‘á»ƒ giáº£m deadlock. Sau khi cÃ³ lock, service kiá»ƒm tra `current + delta >= 0` rá»“i má»›i append
ledger row.

Khi Ä‘áº·t Ä‘Æ¡n, variant Ä‘Æ°á»£c khÃ³a trÆ°á»›c ingredient. Recipe API cÅ©ng khÃ³a theo thá»© tá»± Ä‘Ã³,
vÃ¬ váº­y recipe khÃ´ng thá»ƒ thay Ä‘á»•i giá»¯a lÃºc order Ä‘á»c Ä‘á»‹nh má»©c vÃ  ghi sale. Order status,
sale/return transactions vÃ  event history cÃ¹ng commit hoáº·c cÃ¹ng rollback.

Idempotency Ä‘Æ°á»£c báº£o vá»‡ báº±ng key unique vÃ  request fingerprint. Sale key Ä‘Æ°á»£c táº¡o á»•n
Ä‘á»‹nh tá»« order item + ingredient; return key tá»« order + sale ID. Partial unique index cÅ©
váº«n ngÄƒn hai sale cho cÃ¹ng order item vÃ  ingredient; unique `reversal_of_id` ngÄƒn hoÃ n
má»™t sale hai láº§n.

## Migration

Revision `f6b9d3e5a7c8`:

- ThÃªm threshold vÃ  soft status cho ingredient.
- Chuáº©n hÃ³a unit báº±ng check constraint.
- ThÃªm actor, reason, fingerprint vÃ  reversal link cho ledger.
- Má»Ÿ rá»™ng transaction type vá»›i `return`.
- KhÃ´ng sá»­a báº¥t ká»³ `quantity_delta` cÅ© nÃ o.
- Backfill metadata cho transaction cÅ©.

Migration sáº½ dá»«ng náº¿u dá»¯ liá»‡u cÅ© dÃ¹ng unit ngoÃ i `g`, `ml`, `piece`, hoáº·c cÃ³ SKU/tÃªn
trÃ¹ng nhau khi so sÃ¡nh khÃ´ng phÃ¢n biá»‡t hoa thÆ°á»ng. Cáº§n rÃ  soÃ¡t dá»¯ liá»‡u vÃ  quyáº¿t Ä‘á»‹nh
mapping thá»§ cÃ´ng; migration khÃ´ng tá»± quy Ä‘á»•i hay gá»™p tá»“n.

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Checklist

- [x] Ingredient CRUD vá»›i soft delete.
- [x] ÄÆ¡n vá»‹ cÆ¡ sá»Ÿ thá»‘ng nháº¥t.
- [x] Recipe theo ProductVariant.
- [x] Nháº­p, waste vÃ  adjustment cÃ³ reason/RBAC/idempotency.
- [x] Ledger chá»‰ append, khÃ´ng cÃ³ API sá»­a/xÃ³a.
- [x] Tá»“n tÃ­nh tá»« tá»•ng ledger.
- [x] Low-stock endpoint.
- [x] Trá»« kho á»Ÿ `placed`, hoÃ n á»Ÿ cancellation.
- [x] Row lock vÃ  thá»© tá»± lock á»•n Ä‘á»‹nh.
- [x] Cháº·n tá»“n Ã¢m.
- [x] Test API, order integration vÃ  cáº¡nh tranh hai connection.
