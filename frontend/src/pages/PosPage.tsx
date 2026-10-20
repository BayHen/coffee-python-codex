import { useEffect, useMemo, useState } from "react";
import { MagnifyingGlass, Minus, Plus, ShoppingCart, Trash } from "@phosphor-icons/react";
import { Button, ErrorState, Input, Loading, PageHeader, Panel } from "../components/ui";
import { idempotencyKey, request } from "../lib/api";
import type { Order, Page, Product, Variant } from "../types";
import { money } from "../types";

type CartLine = { variant: Variant; product: string; quantity: number };
export function PosPage() {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [search, setSearch] = useState("");
  const [discount, setDiscount] = useState("0");
  const [reason, setReason] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<Order | null>(null);
  useEffect(() => { request<Page<Product>>("/products?is_active=true&page_size=100").then((p) => setProducts(p.items)).catch((e) => setError(e.message)); }, []);
  const shown = products?.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()) || p.variants.some((v) => v.sku.toLowerCase().includes(search.toLowerCase()))) ?? [];
  const subtotal = useMemo(() => cart.reduce((sum, line) => sum + Number(line.variant.price) * line.quantity, 0), [cart]);
  const total = subtotal * (1 - Math.min(Number(discount) || 0, 20) / 100);
  function add(product: Product, variant: Variant) { setCreated(null); setCart((old) => { const found = old.find((l) => l.variant.id === variant.id); return found ? old.map((l) => l.variant.id === variant.id ? { ...l, quantity: Math.min(l.quantity + 1, 100) } : l) : [...old, { variant, product: product.name, quantity: 1 }]; }); }
  function quantity(id: number, delta: number) { setCart((old) => old.map((l) => l.variant.id === id ? { ...l, quantity: l.quantity + delta } : l).filter((l) => l.quantity > 0)); }
  async function createOrder() {
    setSubmitting(true); setError("");
    try {
      const value = Number(discount) || 0;
      const order = await request<Order>("/orders", { method: "POST", headers: { "Idempotency-Key": idempotencyKey("pos-order") }, body: JSON.stringify({ customer_id: customerId ? Number(customerId) : null, items: cart.map((l) => ({ variant_id: l.variant.id, quantity: l.quantity })), discount_percent: value, discount_reason: value > 0 ? reason : null }) });
      setCreated(order); setCart([]); setDiscount("0"); setReason(""); setCustomerId("");
    } catch (e) { setError(e instanceof Error ? e.message : "Không tạo được đơn"); } finally { setSubmitting(false); }
  }
  return <><PageHeader title="Bán hàng" description="Chọn món nhanh; giá và tổng tiền cuối cùng luôn do server tính." />
    <div className="grid gap-5 xl:grid-cols-[1fr_25rem]">
      <section><Panel className="mb-4 flex items-center gap-2 p-3"><MagnifyingGlass className="ml-2 text-stone-500" /><Input aria-label="Tìm món" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Tên món hoặc SKU" /></Panel>
        {error && !products ? <Panel><ErrorState message={error} /></Panel> : !products ? <Panel><Loading /></Panel> : <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">{shown.flatMap((product) => product.variants.filter((v) => v.is_active).map((variant) => <button key={variant.id} onClick={() => add(product, variant)} className="panel group p-4 text-left hover:border-coffee"><div className="mb-5 flex items-start justify-between"><span className="text-xs font-bold text-stone-500">{variant.sku}</span><Plus className="text-coffee opacity-60 group-hover:opacity-100" /></div><strong className="block text-lg">{product.name}</strong><span className="text-sm text-stone-500">{variant.name}</span><span className="mt-3 block font-bold text-coffee">{money(variant.price)}</span></button>))}</div>}
      </section>
      <Panel className="h-fit overflow-hidden xl:sticky xl:top-6"><div className="flex items-center gap-2 border-b border-stone-200 p-4"><ShoppingCart size={21} /><h2 className="font-serif text-xl font-bold">Đơn hiện tại</h2><span className="ml-auto text-sm text-stone-500">{cart.length} món</span></div>
        <div className="max-h-[42dvh] overflow-auto p-4">{cart.length === 0 ? <div className="py-12 text-center text-sm text-stone-500">Chọn món từ danh sách để bắt đầu.</div> : <div className="space-y-4">{cart.map((line) => <div key={line.variant.id}><div className="flex justify-between gap-2"><div><strong className="block text-sm">{line.product}</strong><span className="text-xs text-stone-500">{line.variant.name}</span></div><strong>{money(Number(line.variant.price) * line.quantity)}</strong></div><div className="mt-2 flex items-center gap-2"><Button aria-label="Giảm số lượng" onClick={() => quantity(line.variant.id, -1)}>{line.quantity === 1 ? <Trash /> : <Minus />}</Button><span className="min-w-7 text-center font-bold">{line.quantity}</span><Button aria-label="Tăng số lượng" onClick={() => quantity(line.variant.id, 1)}><Plus /></Button></div></div>)}</div>}</div>
        <div className="space-y-3 border-t border-stone-200 bg-[#fbfaf7] p-4"><label><span className="label">Mã khách hàng, không bắt buộc</span><Input type="number" min="1" value={customerId} onChange={(e) => setCustomerId(e.target.value)} /></label><div className="grid grid-cols-2 gap-2"><label><span className="label">Giảm giá %</span><Input type="number" min="0" max="20" step="0.01" value={discount} onChange={(e) => setDiscount(e.target.value)} /></label>{Number(discount) > 0 && <label><span className="label">Lý do</span><Input value={reason} minLength={3} onChange={(e) => setReason(e.target.value)} /></label>}</div><div className="flex justify-between text-sm"><span>Tạm tính</span><span>{money(subtotal)}</span></div><div className="flex justify-between text-xl font-bold"><span>Dự kiến</span><span>{money(total)}</span></div>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}{created && <p role="status" className="rounded-lg bg-green-50 p-3 text-sm font-bold text-green-800">Đã tạo đơn #{created.id}. Tổng server: {money(created.total_amount)}</p>}<Button className="btn-primary w-full" disabled={cart.length === 0 || submitting || (Number(discount) > 0 && reason.trim().length < 3)} onClick={() => void createOrder()}>{submitting ? "Đang tạo..." : "Tạo đơn nháp"}</Button></div>
      </Panel>
    </div>
  </>;
}
