import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ArrowClockwise, CreditCard, Minus, Plus, Trash } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { Button, Empty, Input, Loading, PageHeader, Panel, StatusBadge } from "../components/ui";
import { idempotencyKey, request } from "../lib/api";
import type { BankTransfer, CafeTable, Page, Product, SessionOrder, SessionPayment, TableSession } from "../types";
import { money } from "../types";

export function OrdersPage() {
  const { canManage } = useAuth();
  const [tables, setTables] = useState<CafeTable[] | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<CafeTable | null>(null);
  const [session, setSession] = useState<TableSession | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tableEditor, setTableEditor] = useState<CafeTable | "new" | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const selectedId = selected?.id;

  const load = useCallback(async () => {
    setError("");
    try {
      const [rows, productPage] = await Promise.all([
        request<CafeTable[]>("/tables"),
        request<Page<Product>>("/products?is_active=true&page_size=100"),
      ]);
      setTables(rows);
      setProducts(Array.isArray(productPage.items) ? productPage.items.map((product) => ({
        ...product,
        base_price: requireOrderPrice(product.base_price, product.name),
        variants: Array.isArray(product.variants) ? product.variants : [],
        toppings: Array.isArray(product.toppings) ? product.toppings : [],
      })) : []);
      if (selectedId) {
        const current = rows.find((table) => table.id === selectedId) ?? null;
        setSelected(current);
        setSession(current?.active_session_id ? await request<TableSession>(`/tables/${current.id}/active-session`) : null);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được sơ đồ bàn"); }
  }, [selectedId]);
  useEffect(() => { void load(); }, [load]);

  async function choose(table: CafeTable) {
    setSelected(table); setError("");
    try { setSession(table.active_session_id ? await request<TableSession>(`/tables/${table.id}/active-session`) : null); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được phiên phục vụ"); }
  }
  async function act(operation: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await operation(); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Thao tác thất bại"); }
    finally { setBusy(false); }
  }
  const draft = session?.orders.find((order) => order.status === "draft");
  const initialConfirmed = session?.orders.some((order) => order.order_type === "initial" && order.status === "confirmed");

  return <><PageHeader title="Bàn & đơn hàng" description="Mỗi bàn có một phiên phục vụ; các lượt gọi thêm được lưu thành đơn riêng." action={<div className="flex gap-2">{canManage && <Button onClick={() => setTableEditor("new")}><Plus />Thêm bàn</Button>}<Button onClick={() => void load()}><ArrowClockwise />Làm mới</Button></div>} />
    {notice && <div role="status" className="mb-4 rounded-lg bg-green-50 p-3 text-green-800">{notice}</div>}{error && <div role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}
    {!tables ? <Panel><Loading /></Panel> : tables.length === 0 ? <Panel><Empty>Chưa có bàn. Admin hoặc Manager có thể tạo bàn đầu tiên.</Empty></Panel> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{tables.map((table) => <button key={table.id} onClick={() => void choose(table)} className={`panel p-5 text-left transition hover:border-coffee ${selected?.id === table.id ? "ring-2 ring-coffee" : ""}`}><div className="flex items-start justify-between"><div><span className="text-xs font-bold uppercase text-stone-500">Bàn {table.table_number}</span><h2 className="mt-1 font-serif text-xl font-bold">{table.name}</h2></div><StatusBadge status={table.status} /></div><p className="mt-6 text-sm text-stone-500">Tổng đã xác nhận</p><strong className="text-xl text-coffee">{money(table.current_bill_total)}</strong>{!table.is_active && <p className="mt-2 text-xs text-red-700">Đã vô hiệu hóa</p>}</button>)}</div>}
    {selected && <Panel className="mt-6 overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 p-5"><div><h2 className="font-serif text-2xl font-bold">Bàn {selected.table_number} · {selected.name}</h2><p className="text-sm text-stone-500">{session ? `Phiên #${session.id} · mở ${new Date(session.opened_at).toLocaleString("vi-VN")}` : "Bàn đang trống"}</p></div><div className="flex gap-2">{canManage && <Button onClick={() => setTableEditor(selected)}>Sửa bàn</Button>}{!session && selected.is_active && <Button className="btn-primary" disabled={busy} onClick={() => void act(() => request(`/tables/${selected.id}/sessions`, { method: "POST" }))}>Mở phiên & tạo đơn đầu</Button>}</div></div>
      {session && <div className="p-5">{draft && <ProductPicker products={products} order={draft} busy={busy} change={(operation) => act(operation)} />}<div className="space-y-4">{session.orders.map((order) => <OrderBlock key={order.id} order={order} busy={busy} change={(operation) => act(operation)} />)}</div><div className="mt-5 grid gap-3 border-t border-stone-200 pt-5 sm:grid-cols-3"><Bill label="Đã xác nhận" value={session.bill.confirmed_subtotal} /><Bill label="Đơn nháp" value={session.bill.draft_subtotal} /><Bill label="Cần thanh toán" value={session.bill.payable_total} /></div><div className="mt-5 flex flex-wrap justify-end gap-2"><Button disabled={busy || !initialConfirmed || Boolean(draft)} onClick={() => void act(() => request(`/sessions/${session.id}/orders`, { method: "POST", body: JSON.stringify({ order_type: "additional" }) }))}><Plus />Add Additional Order</Button><Button className="btn-primary" disabled={busy || Number(session.bill.payable_total) <= 0 || Boolean(draft?.items.length)} onClick={() => setCheckoutOpen(true)}><CreditCard />Checkout</Button></div></div>}
    </Panel>}
    {tableEditor && <TableDialog table={tableEditor === "new" ? undefined : tableEditor} close={() => setTableEditor(null)} saved={async () => { setTableEditor(null); await load(); }} />}
    {checkoutOpen && session && <CheckoutDialog session={session} close={() => setCheckoutOpen(false)} paid={async (payment) => { setCheckoutOpen(false); setSession(null); setSelected(null); setNotice(`Thanh toán thành công · ${payment.receipt_number}`); await load(); }} />}
  </>;
}

function CheckoutDialog({ session, close, paid }: { session: TableSession; close: () => void; paid: (payment: SessionPayment) => Promise<void> }) {
  const [method, setMethod] = useState<"cash" | "bank_transfer">("cash"); const [cash, setCash] = useState(""); const [verified, setVerified] = useState(false); const [bank, setBank] = useState<BankTransfer | null>(null); const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const [key] = useState(() => idempotencyKey(`checkout-${session.id}`));
  const total = Number(session.bill.payable_total); const change = Math.max(Number(cash || 0) - total, 0);
  useEffect(() => { if (method === "bank_transfer" && !bank) request<BankTransfer>(`/sessions/${session.id}/bank-transfer`).then(setBank).catch((reason) => setError(reason instanceof Error ? reason.message : "Không tải được VietQR")); }, [bank, method, session.id]);
  async function confirmPayment() { setBusy(true); setError(""); try { const payment = await request<SessionPayment>(`/sessions/${session.id}/checkout`, { method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify(method === "cash" ? { method, cash_received: cash } : { method, transfer_confirmed: verified, transfer_reference: bank?.payment_reference }) }); await paid(payment); } catch (reason) { setError(reason instanceof Error ? reason.message : "Thanh toán thất bại"); } finally { setBusy(false); } }
  const confirmed = session.orders.filter((order) => order.status === "confirmed");
  return <div className="dialog-backdrop" role="presentation"><div className="dialog max-w-2xl" role="dialog" aria-modal="true" aria-label="Thanh toán"><h2 className="font-serif text-2xl font-bold">Thanh toán phiên #{session.id}</h2><div className="mt-4 max-h-64 overflow-auto">{confirmed.flatMap((order) => order.items).map((item) => <div key={item.id} className="flex justify-between border-b border-stone-100 py-2"><span>{item.quantity}× {item.product_name} · {item.variant_name}{item.topping_snapshots?.length ? ` · ${item.topping_snapshots.map((value) => value.name).join(", ")}` : ""}<small className="block">{money(item.unit_price)} / món</small></span><b>{money(item.line_total)}</b></div>)}</div><div className="mt-3 flex justify-between text-xl font-bold"><span>Tổng tiền</span><span>{money(total)}</span></div><div className="mt-4 flex gap-2"><Button className={method === "cash" ? "btn-primary" : ""} onClick={() => { setMethod("cash"); setVerified(false); }}>CASH</Button><Button className={method === "bank_transfer" ? "btn-primary" : ""} onClick={() => setMethod("bank_transfer")}>BANK TRANSFER</Button></div>
    {method === "cash" ? <div className="mt-4 grid gap-3 sm:grid-cols-2"><label><span className="label">Tiền khách đưa</span><Input type="number" min={total} step="0.01" value={cash} onChange={(event) => setCash(event.target.value)} /></label><div><span className="label">Tiền thừa</span><strong className="block text-xl">{money(change)}</strong></div></div> : <div className="mt-4 text-center">{!bank ? <Loading /> : !bank.available ? <p className="text-red-700">Chuyển khoản chưa được cấu hình trên server.</p> : <><img className="mx-auto size-56" src={bank.qr_image_url ?? undefined} alt="VietQR thanh toán" /><p><b>{bank.bank_name}</b> · {bank.account_number}</p><p>{bank.account_holder}</p><p>Nội dung: <b>{bank.payment_reference}</b></p><label className="mt-3 flex justify-center gap-2"><input type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} /> Tôi đã kiểm tra tiền thực sự được nhận</label></>}</div>}
    {error && <p role="alert" className="mt-3 text-red-700">{error}</p>}<div className="mt-6 flex justify-end gap-2"><Button onClick={close}>Hủy</Button><Button className="btn-primary" disabled={busy || (method === "cash" ? Number(cash) < total : !bank?.available || !verified)} onClick={() => void confirmPayment()}>{busy ? "Đang xử lý..." : "Confirm Payment"}</Button></div></div></div>;
}

function Bill({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-stone-100 p-4"><span className="text-sm text-stone-500">{label}</span><strong className="mt-1 block text-xl">{money(value)}</strong></div>; }

function requireOrderPrice(value: string | undefined, productName: string): string {
  if (value == null || value.trim() === "" || !Number.isFinite(Number(value))) {
    throw new Error(`API thiếu giá cơ bản hợp lệ cho sản phẩm ${productName}`);
  }
  return value;
}

function ProductPicker({ products, order, busy, change }: { products: Product[]; order: SessionOrder; busy: boolean; change: (operation: () => Promise<unknown>) => Promise<void> }) {
  const [productId, setProductId] = useState(""); const [sizeId, setSizeId] = useState(""); const [toppings, setToppings] = useState<number[]>([]); const [quantity, setQuantity] = useState(1);
  const product = products.find((item) => item.id === Number(productId));
  const variants = product?.variants ?? [];
  const availableToppings = (product?.toppings ?? []).filter((item) => item.is_active);
  const size = variants.find((item) => item.id === Number(sizeId));
  const basePrice = Number(product?.base_price ?? 0);
  const unitPrice = basePrice + Number(size?.price ?? 0) + availableToppings.filter((item) => toppings.includes(item.id)).reduce((sum, item) => sum + Number(item.price), 0);
  return <section className="mb-5 rounded-xl bg-stone-100 p-4"><h3 className="font-serif text-xl font-bold">Thêm món vào đơn nháp #{order.sequence_number}</h3><div className="mt-3 grid gap-3 md:grid-cols-4"><select className="field" aria-label="Chọn sản phẩm" value={productId} onChange={(event) => { const id = event.target.value; const selectedProduct = products.find((item) => item.id === Number(id)); const activeVariants = selectedProduct?.variants.filter((item) => item.is_active) ?? []; setProductId(id); setSizeId(activeVariants.length === 1 ? String(activeVariants[0].id) : ""); setToppings([]); }}><option value="">Chọn sản phẩm</option>{products.map((item) => <option key={item.id} value={item.id}>{item.name} · giá gốc {money(item.base_price)}</option>)}</select><select className="field" aria-label="Chọn size" value={sizeId} onChange={(event) => setSizeId(event.target.value)} disabled={!product}><option value="">Chọn size</option>{variants.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name} · {money(basePrice + Number(item.price))}</option>)}</select><Input aria-label="Số lượng" type="number" min="1" max="100" value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} /><Button className="btn-primary" disabled={busy || !size || quantity < 1} onClick={() => void change(() => request(`/orders/${order.id}/items`, { method: "POST", body: JSON.stringify({ variant_id: Number(sizeId), topping_ids: toppings, quantity }) }))}>Thêm · {money(unitPrice * quantity)}</Button></div>{availableToppings.length > 0 && <div className="mt-3 flex flex-wrap gap-3">{availableToppings.map((item) => <label key={item.id} className="flex items-center gap-2"><input type="checkbox" checked={toppings.includes(item.id)} onChange={(event) => setToppings((old) => event.target.checked ? [...old, item.id] : old.filter((id) => id !== item.id))} />{item.name} +{money(item.price)}</label>)}</div>}</section>;
}

function OrderBlock({ order, busy, change }: { order: SessionOrder; busy: boolean; change: (operation: () => Promise<unknown>) => Promise<void> }) {
  const editable = order.status === "draft";
  return <section className="rounded-xl border border-stone-200 p-4"><div className="flex items-center justify-between gap-3"><div><strong>Đơn #{order.sequence_number} · {order.order_type === "initial" ? "Initial Order" : "Additional Order"}</strong><div className="mt-1"><StatusBadge status={order.status} /></div></div><strong>{money(order.total_amount)}</strong></div><div className="mt-3 space-y-2">{order.items.length === 0 ? <p className="text-sm text-stone-500">Chưa có món. Chọn sản phẩm ở phía trên.</p> : order.items.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-stone-100 pt-2"><span>{item.product_name} · {item.variant_name}{item.topping_snapshots?.length ? ` · ${item.topping_snapshots.map((topping) => topping.name).join(", ")}` : ""}</span><div className="flex items-center gap-2"><span>{money(item.line_total)}</span>{editable && <><Button aria-label="Giảm số lượng" disabled={busy} onClick={() => item.quantity === 1 ? void change(() => request(`/orders/${order.id}/items/${item.id}`, { method: "DELETE" })) : void change(() => request(`/orders/${order.id}/items/${item.id}`, { method: "PATCH", body: JSON.stringify({ quantity: item.quantity - 1 }) }))}>{item.quantity === 1 ? <Trash /> : <Minus />}</Button><b>{item.quantity}</b><Button aria-label="Tăng số lượng" disabled={busy || item.quantity >= 100} onClick={() => void change(() => request(`/orders/${order.id}/items/${item.id}`, { method: "PATCH", body: JSON.stringify({ quantity: item.quantity + 1 }) }))}><Plus /></Button></>}</div></div>)}</div>{editable && <div className="mt-3 flex justify-end"><Button className="btn-primary" disabled={busy || order.items.length === 0} onClick={() => void change(() => request(`/orders/${order.id}/confirm`, { method: "POST" }))}>Xác nhận đơn</Button></div>}</section>;
}

function TableDialog({ table, close, saved }: { table?: CafeTable; close: () => void; saved: () => Promise<void> }) {
  const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setSaving(true); const data = new FormData(event.currentTarget); try { await request(table ? `/tables/${table.id}` : "/tables", { method: table ? "PATCH" : "POST", body: JSON.stringify({ table_number: data.get("table_number"), name: data.get("name") }) }); await saved(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Không thể lưu bàn"); } finally { setSaving(false); } }
  return <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && close()}><form className="dialog" role="dialog" aria-modal="true" aria-label={table ? "Sửa bàn" : "Thêm bàn"} onSubmit={submit}><h2 className="font-serif text-2xl font-bold">{table ? "Sửa bàn" : "Thêm bàn"}</h2><div className="mt-5 space-y-4"><label><span className="label">Số bàn</span><Input name="table_number" defaultValue={table?.table_number} maxLength={20} required autoFocus /></label><label><span className="label">Tên bàn</span><Input name="name" defaultValue={table?.name} maxLength={100} required /></label></div>{error && <p role="alert" className="mt-4 text-red-700">{error}</p>}<div className="mt-6 flex justify-end gap-2"><Button type="button" onClick={close}>Hủy</Button><Button className="btn-primary" disabled={saving}>Lưu</Button></div></form></div>;
}
