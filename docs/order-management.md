# Task 5 â€” Order Management

> Standalone order endpoints remain compatible. Dine-in initial/additional orders use
> table sessions documented in [table-order-management.md](table-order-management.md).

## State machine

```mermaid
stateDiagram-v2
    [*] --> draft: create order
    draft --> draft: replace items / discount
    draft --> placed: confirm order
    draft --> cancelled: Manager/Admin cancels
    placed --> paid: simulated payment succeeds
    placed --> placed: simulated payment fails
    placed --> cancelled: Manager/Admin cancels
    paid --> [*]
    cancelled --> [*]
```

`paid` vÃ  `cancelled` lÃ  tráº¡ng thÃ¡i cuá»‘i. Staff cÃ³ thá»ƒ táº¡o, sá»­a draft, xÃ¡c nháº­n vÃ 
thanh toÃ¡n; chá»‰ Manager/Admin cÃ³ thá»ƒ há»§y. Má»—i láº§n táº¡o, sá»­a, Ä‘á»•i tráº¡ng thÃ¡i hoáº·c thá»­
thanh toÃ¡n Ä‘á»u ghi `order_events`.

## API

| Method | Path | MÃ´ táº£ |
| --- | --- | --- |
| POST | `/orders` | Táº¡o draft; báº¯t buá»™c header `Idempotency-Key` |
| GET | `/orders` | Danh sÃ¡ch, lá»c `status`, pagination |
| GET | `/orders/{id}` | Chi tiáº¿t gá»“m items, events, payments |
| PUT | `/orders/{id}` | Thay toÃ n bá»™ items/discount khi cÃ²n draft |
| POST | `/orders/{id}/transitions` | Chuyá»ƒn sang `placed` hoáº·c `cancelled` |
| POST | `/orders/{id}/payments` | Thanh toÃ¡n mÃ´ phá»ng; báº¯t buá»™c idempotency key |

VÃ­ dá»¥ táº¡o Ä‘Æ¡n:

```http
POST /orders
Authorization: Bearer <access-token>
Idempotency-Key: pos-terminal-01-000001
Content-Type: application/json
```

```json
{
  "customer_id": null,
  "items": [
    {"variant_id": 10, "quantity": 2},
    {"variant_id": 12, "quantity": 1}
  ],
  "discount_percent": "10.00",
  "discount_reason": "Opening promotion"
}
```

Client khÃ´ng Ä‘Æ°á»£c gá»­i tÃªn, giÃ¡, subtotal, discount amount hoáº·c total. Request cÃ³
field thá»«a bá»‹ tráº£ 422. Server khÃ³a variant, kiá»ƒm tra product vÃ  variant cÃ²n bÃ¡n, rá»“i
chá»¥p `product_name`, `variant_name`, `sku`, `unit_price` vÃ  `line_total`.

VÃ­ dá»¥ response rÃºt gá»n:

```json
{
  "id": 42,
  "status": "draft",
  "subtotal_amount": "11.45",
  "discount_percent": "10.00",
  "discount_amount": "1.15",
  "total_amount": "10.30",
  "items": [
    {
      "variant_id": 10,
      "product_name": "Latte",
      "variant_name": "Size M",
      "sku": "LATTE-M",
      "quantity": 2,
      "unit_price": "4.55",
      "line_total": "9.10"
    }
  ]
}
```

Thanh toÃ¡n mÃ´ phá»ng:

```http
POST /orders/42/payments
Idempotency-Key: payment-terminal-01-000001
```

```json
{"method": "card_demo", "outcome": "succeeded"}
```

`method` chá»‰ nháº­n `cash` hoáº·c `card_demo`; `outcome` cho phÃ©p test `succeeded` vÃ 
`failed`. API khÃ´ng káº¿t ná»‘i cá»•ng thanh toÃ¡n vÃ  khÃ´ng xá»­ lÃ½ tiá»n tháº­t.

## Tiá»n, discount vÃ  transaction

- Táº¥t cáº£ sá»‘ tiá»n dÃ¹ng `Decimal`/`NUMERIC`, lÃ m trÃ²n `ROUND_HALF_UP` Ä‘áº¿n 2 chá»¯ sá»‘.
- Discount lÃ  pháº§n trÄƒm tá»« 0 Ä‘áº¿n 20. Discount dÆ°Æ¡ng báº¯t buá»™c cÃ³ lÃ½ do.
- `subtotal = SUM(unit_price Ã— quantity)`.
- `discount_amount = round(subtotal Ã— discount_percent / 100, 2)`.
- `total = subtotal - discount_amount`.
- Subtotal pháº£i dÆ°Æ¡ng. Database kiá»ƒm tra thÃ nh pháº§n tá»•ng, line total vÃ  giá»›i háº¡n discount.

Táº¡o Ä‘Æ¡n cháº¡y trong má»™t `session.begin()`: kiá»ƒm tra idempotency, khÃ³a cÃ¡c variant theo
thá»© tá»± ID, chá»¥p giÃ¡/tÃªn, tÃ­nh tá»•ng, ghi order/items/event rá»“i commit cÃ¹ng lÃºc. Viá»‡c
khÃ³a cáº£ product vÃ  variant ngÄƒn cáº­p nháº­t menu chen giá»¯a lÃºc kiá»ƒm tra tráº¡ng thÃ¡i vÃ 
chá»¥p giÃ¡.

Thanh toÃ¡n khÃ³a dÃ²ng order báº±ng `SELECT FOR UPDATE`. Hai request Ä‘á»“ng thá»i vÃ¬ váº­y
Ä‘Æ°á»£c tuáº§n tá»± hÃ³a; request thá»© hai tháº¥y order Ä‘Ã£ `paid` vÃ  bá»‹ tá»« chá»‘i. Unique key trÃªn
`payments.idempotency_key` chá»‘ng replay, cÃ²n partial unique index trÃªn má»™t payment
`succeeded` má»—i order lÃ  lá»›p báº£o vá»‡ cuá»‘i á»Ÿ database. Retry cÃ¹ng key vÃ  cÃ¹ng payload
tráº£ láº¡i báº£n ghi cÅ©; dÃ¹ng láº¡i key vá»›i payload khÃ¡c tráº£ 409.

Task nÃ y khÃ´ng ghi `inventory_transactions` vÃ  khÃ´ng trá»« nguyÃªn liá»‡u.

## Lá»—i thÆ°á»ng gáº·p

- Gá»­i giÃ¡ hoáº·c total tá»« POS: 422 vÃ¬ request cáº¥m field thá»«a.
- DÃ¹ng má»™t variant hai láº§n: 422; tÄƒng `quantity` trÃªn má»™t dÃ²ng.
- Discount trÃªn 20% hoáº·c thiáº¿u lÃ½ do: 422.
- Product/variant Ä‘Ã£ ngá»«ng bÃ¡n: 409 `variant_unavailable`.
- Sá»­a Ä‘Æ¡n sau khi placed: 409 `order_not_editable`.
- Chuyá»ƒn tráº¡ng thÃ¡i sai: 409 `invalid_order_transition`.
- Thanh toÃ¡n draft/paid/cancelled: 409 `order_not_payable`.
- DÃ¹ng láº¡i idempotency key cho payload khÃ¡c: 409 `idempotency_key_reused`.
- Staff há»§y Ä‘Æ¡n: 403.

## Cháº¡y migration vÃ  test

Äá»c revision `e5a8c2d4f6b7` trÆ°á»›c khi Ã¡p dá»¥ng. Migration backfill snapshot vÃ  totals
cho dá»¯ liá»‡u cÅ©; downgrade bá»‹ cháº·n vÃ¬ cáº§n káº¿ hoáº¡ch báº£o toÃ n lá»‹ch sá»­.

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev'
.\.venv\Scripts\python.exe -m alembic upgrade head

$env:TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/coffee_shop_dev_test'
.\.venv\Scripts\python.exe -m pytest
```

Test concurrency táº¡o dá»¯ liá»‡u cÃ³ suffix ngáº«u nhiÃªn trong database `_test`, cháº¡y hai
payment báº±ng hai connection tháº­t, xÃ¡c nháº­n chá»‰ má»™t payment thÃ nh cÃ´ng, rá»“i xÃ³a Ä‘Ãºng
cÃ¡c báº£n ghi test Ä‘Ã£ táº¡o.

## Checklist

- [x] Server láº¥y giÃ¡ hiá»‡n táº¡i vÃ  tá»± tÃ­nh tá»•ng.
- [x] Snapshot tÃªn, SKU, giÃ¡ vÃ  line total.
- [x] Decimal, discount validation vÃ  database constraints.
- [x] State machine vÃ  event history.
- [x] Soft history Ä‘á»™c láº­p vá»›i thay Ä‘á»•i menu.
- [x] Idempotency cho create order vÃ  payment.
- [x] Row lock cÃ¹ng unique constraints chá»‘ng double payment.
- [x] KhÃ´ng trá»« kho trong Task 5.

## CÃ¢u há»i kiáº¿n thá»©c

1. VÃ¬ sao unique idempotency key váº«n cáº§n request fingerprint?
2. `SELECT FOR UPDATE` báº£o vá»‡ double payment khÃ¡c gÃ¬ partial unique index?
3. VÃ¬ sao `OrderItem` pháº£i lÆ°u snapshot thay vÃ¬ luÃ´n join giÃ¡ hiá»‡n táº¡i?
4. Äiá»u gÃ¬ xáº£y ra náº¿u tÃ­nh tiá»n báº±ng `float` vÃ  lÃ m trÃ²n á»Ÿ cuá»‘i?
5. VÃ¬ sao event vÃ  thay Ä‘á»•i tráº¡ng thÃ¡i pháº£i commit trong cÃ¹ng transaction?
