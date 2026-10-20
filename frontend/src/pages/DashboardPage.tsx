import { useEffect, useState } from "react";
import { Archive, Coffee, Package, Receipt } from "@phosphor-icons/react";
import { ErrorState, Loading, PageHeader, Panel, StatusBadge } from "../components/ui";
import { request } from "../lib/api";
import type { Ingredient, Order, Page, Product } from "../types";
import { money } from "../types";

type Summary = { products: Page<Product>; orders: Page<Order>; low: Page<Ingredient> };
export function DashboardPage() {
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  async function load() {
    setError("");
    try {
      const [products, orders, low] = await Promise.all([
        request<Page<Product>>("/products?page_size=1"),
        request<Page<Order>>("/orders?page_size=5"),
        request<Page<Ingredient>>("/ingredients/low-stock?page_size=100"),
      ]);
      setData({ products, orders, low });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được dữ liệu"); }
  }
  useEffect(() => { void load(); }, []);
  const stats = data ? [
    { Icon: Package, label: "Sản phẩm", value: data.products.total, note: "Trong danh mục" },
    { Icon: Receipt, label: "Đơn gần đây", value: data.orders.total, note: "Tổng số đơn" },
    { Icon: Archive, label: "Cần nhập kho", value: data.low.total, note: "Dưới ngưỡng" },
    { Icon: Coffee, label: "Đơn đang mở", value: data.orders.items.filter((o) => o.status === "draft" || o.status === "placed").length, note: "Trong 5 đơn mới" },
  ] : [];
  return <><PageHeader title="Tổng quan" description="Nhịp vận hành hiện tại của cửa hàng." />
    {error ? <Panel><ErrorState message={error} retry={() => void load()} /></Panel> : !data ? <Panel><Loading /></Panel> : <>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map(({ Icon, label, value, note }) => <Panel key={label} className="p-5"><div className="mb-6 flex items-center justify-between text-stone-500"><span className="text-sm font-bold">{label}</span><Icon size={21} /></div><strong className="font-serif text-4xl">{value}</strong><p className="mt-1 text-sm text-stone-500">{note}</p></Panel>)}
      </section>
      <section className="mt-6 grid gap-6 xl:grid-cols-[1.45fr_.55fr]">
        <Panel className="overflow-hidden"><div className="flex items-center justify-between p-5"><h2 className="font-serif text-xl font-bold">Đơn mới nhất</h2><span className="text-sm text-stone-500">Cập nhật từ API</span></div>{data.orders.items.length === 0 ? <div className="state">Chưa có đơn hàng.</div> : <div className="overflow-x-auto"><table className="data-table"><thead><tr><th>Mã</th><th>Trạng thái</th><th>Tổng</th><th>Thời gian</th></tr></thead><tbody>{data.orders.items.map((order) => <tr key={order.id}><td data-label="Mã" className="font-bold">#{order.id}</td><td data-label="Trạng thái"><StatusBadge status={order.status} /></td><td data-label="Tổng">{money(order.total_amount)}</td><td data-label="Thời gian" className="text-sm text-stone-500">{new Date(order.created_at).toLocaleString("vi-VN")}</td></tr>)}</tbody></table></div>}</Panel>
        <Panel className="p-5"><h2 className="font-serif text-xl font-bold">Tồn kho thấp</h2><div className="mt-5 space-y-4">{data.low.items.length === 0 ? <p className="text-sm text-stone-500">Không có cảnh báo.</p> : data.low.items.slice(0, 6).map((item) => <div key={item.id} className="flex items-center justify-between gap-3"><div><strong className="block text-sm">{item.name}</strong><span className="text-xs text-stone-500">{item.sku}</span></div><span className="font-mono text-sm font-bold text-red-700">{item.current_stock} {item.unit}</span></div>)}</div></Panel>
      </section>
    </>}
  </>;
}
