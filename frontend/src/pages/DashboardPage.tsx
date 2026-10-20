import { useCallback, useEffect, useState } from "react";
import { Archive, ChartBar, CurrencyCircleDollar, Package, Receipt, TrendUp } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, Loading, PageHeader, Panel } from "../components/ui";
import { request } from "../lib/api";
import { normalizeRevenueSummary, type RevenueSummaryResponse } from "../lib/reporting";
import type { DailyRevenueReport, Ingredient, Order, Page, Product, RevenueSummary, TopProductsReport } from "../types";
import { money } from "../types";

type Operations = { products: Page<Product>; orders: Page<Order>; low: Page<Ingredient> };
type Reports = { summary: RevenueSummary; daily: DailyRevenueReport; top: TopProductsReport };

function isoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function initialRange() {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 29);
  return { from: isoDate(start), to: isoDate(end) };
}

function RevenueDashboard() {
  const initial = initialRange();
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [data, setData] = useState<Reports | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    const query = new URLSearchParams({ date_from: from, date_to: to, timezone: "Asia/Ho_Chi_Minh" });
    try {
      const [summary, daily, top] = await Promise.all([
        request<RevenueSummaryResponse>(`/reports/revenue/summary?${query}`),
        request<DailyRevenueReport>(`/reports/revenue/daily?${query}`),
        request<TopProductsReport>(`/reports/top-products?${query}&limit=8`),
      ]);
      setData({
        summary: normalizeRevenueSummary(summary),
        daily,
        top,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không tải được báo cáo");
    } finally {
      setLoading(false);
    }
  }, [from, to]);

  useEffect(() => { void load(); }, [load]);
  const maxRevenue = Math.max(...(data?.daily.items.map((item) => Number(item.revenue)) ?? [0]), 1);
  const maxQuantity = Math.max(...(data?.top.items.map((item) => item.quantity_sold) ?? [0]), 1);

  return <>
    <div className="mb-5 flex flex-wrap items-end gap-3">
      <label><span className="label">Từ ngày</span><input aria-label="Từ ngày" className="field" type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} /></label>
      <label><span className="label">Đến ngày</span><input aria-label="Đến ngày" className="field" type="date" value={to} min={from} onChange={(event) => setTo(event.target.value)} /></label>
      <button className="btn" type="button" onClick={() => void load()}>Làm mới</button>
      <span className="pb-2 text-xs text-stone-500">Múi giờ Asia/Ho_Chi_Minh</span>
    </div>
    {error ? <Panel><ErrorState message={error} retry={() => void load()} /></Panel> : loading || !data ? <Panel><Loading /></Panel> : <>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { Icon: CurrencyCircleDollar, label: "Doanh thu", value: money(data.summary.total_revenue), note: "Thanh toán thành công" },
          { Icon: Receipt, label: "Phiên đã thanh toán", value: data.summary.paid_session_count, note: `${data.summary.valid_order_count} giao dịch thành công` },
          { Icon: TrendUp, label: "Tiền mặt", value: money(data.summary.cash_revenue), note: "Doanh thu CASH" },
          { Icon: Archive, label: "Chuyển khoản", value: money(data.summary.bank_transfer_revenue), note: "Doanh thu BANK TRANSFER" },
        ].map(({ Icon, label, value, note }) => <Panel key={label} className="p-5"><div className="mb-5 flex items-center justify-between text-stone-500"><span className="text-sm font-bold">{label}</span><Icon size={21} /></div><strong className="font-serif text-3xl">{value}</strong><p className="mt-1 text-sm text-stone-500">{note}</p></Panel>)}
      </section>
      <section className="mt-6 grid gap-6 xl:grid-cols-[1.45fr_.55fr]">
        <Panel className="p-5"><div className="mb-6 flex items-center justify-between"><h2 className="font-serif text-xl font-bold">Doanh thu theo ngày</h2><ChartBar size={22} /></div><div className="flex h-64 items-end gap-1 overflow-x-auto border-b border-stone-200 pb-2" aria-label="Biểu đồ doanh thu theo ngày">{data.daily.items.map((item) => <div key={item.date} className="flex min-w-8 flex-1 flex-col items-center justify-end gap-2" title={`${item.date}: ${money(item.revenue)}`}><span className="text-[10px] text-stone-500">{item.order_count}</span><div className="w-full min-w-5 rounded-t bg-coffee" style={{ height: `${Math.max((Number(item.revenue) / maxRevenue) * 180, Number(item.revenue) > 0 ? 4 : 0)}px` }} /><span className="text-[10px] text-stone-500">{item.date.slice(5)}</span></div>)}</div></Panel>
        <Panel className="p-5"><h2 className="font-serif text-xl font-bold">Sản phẩm bán chạy</h2><div className="mt-5 space-y-5">{data.top.items.length === 0 ? <p className="text-sm text-stone-500">Chưa có sản phẩm đã thanh toán.</p> : data.top.items.map((item) => <div key={`${item.sku}-${item.variant_name}`}><div className="mb-1 flex justify-between gap-3 text-sm"><strong>{item.product_name} · {item.variant_name}</strong><span>{item.quantity_sold}</span></div><div className="h-2 overflow-hidden rounded-full bg-stone-200"><div className="h-full rounded-full bg-leaf" style={{ width: `${(item.quantity_sold / maxQuantity) * 100}%` }} /></div><p className="mt-1 text-xs text-stone-500">{money(item.gross_item_sales)} trước giảm giá</p></div>)}</div></Panel>
      </section>
    </>}
  </>;
}

function OperationsDashboard() {
  const [data, setData] = useState<Operations | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try {
      const [products, orders, low] = await Promise.all([
        request<Page<Product>>("/products?page_size=1"),
        request<Page<Order>>("/orders?page_size=5"),
        request<Page<Ingredient>>("/ingredients/low-stock?page_size=100"),
      ]);
      setData({ products, orders, low });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được dữ liệu"); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  if (error) return <Panel><ErrorState message={error} retry={() => void load()} /></Panel>;
  if (!data) return <Panel><Loading /></Panel>;
  const stats = [
    { Icon: Package, label: "Sản phẩm", value: data.products.total },
    { Icon: Receipt, label: "Tổng số đơn", value: data.orders.total },
    { Icon: Archive, label: "Cần nhập kho", value: data.low.total },
  ];
  return <section className="grid gap-3 sm:grid-cols-3">{stats.map(({ Icon, label, value }) => <Panel key={label} className="p-5"><div className="mb-5 flex justify-between text-stone-500"><span className="text-sm font-bold">{label}</span><Icon size={21} /></div><strong className="font-serif text-4xl">{value}</strong></Panel>)}</section>;
}

export function DashboardPage() {
  const { canManage } = useAuth();
  return <><PageHeader title="Tổng quan" description={canManage ? "Doanh thu từ các thanh toán hợp lệ." : "Nhịp vận hành hiện tại của cửa hàng."} />{canManage ? <RevenueDashboard /> : <OperationsDashboard />}</>;
}
