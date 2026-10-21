import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { MagnifyingGlass, Minus, Plus, X } from "@phosphor-icons/react";
import { ApiError, idempotencyKey, request } from "../lib/api";
import type { Page, Product, SessionOrder, Variant } from "../types";
import { money } from "../types";
import { Button, Input, Loading } from "./ui";

type ProductPickerProps = {
  order: SessionOrder;
  disabled: boolean;
  added: (priceChanged: boolean) => Promise<void>;
};

export function ProductPicker({ order, disabled, added }: ProductPickerProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [open, setOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();

  useEffect(() => {
    const search = query.trim();
    if (!search) {
      setResults([]);
      setLoading(false);
      setSearchError("");
      setOpen(false);
      return;
    }
    setResults([]);
    setLoading(true);
    setSearchError("");
    setOpen(true);
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          search,
          is_active: "true",
          page_size: "20",
        });
        const response = await request<Page<Product>>(`/products?${params}`, {
          signal: controller.signal,
        });
        const products = Array.isArray(response.items)
          ? response.items.filter((product) => product.is_active).map(normalizeProduct)
          : [];
        setResults(products);
        setActiveIndex(products.length > 0 ? 0 : -1);
        setOpen(true);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setResults([]);
        setSearchError(reason instanceof Error ? reason.message : "Không thể tìm sản phẩm");
        setOpen(true);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  function choose(product: Product) {
    setSelectedProduct(product);
    setOpen(false);
  }

  function handleKeys(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!results.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) => {
        const direction = event.key === "ArrowDown" ? 1 : -1;
        return (current + direction + results.length) % results.length;
      });
    }
    if (event.key === "Enter" && open && activeIndex >= 0) {
      event.preventDefault();
      choose(results[activeIndex]);
    }
  }

  function finish() {
    setSelectedProduct(null);
    setQuery("");
    setResults([]);
    requestAnimationFrame(() => searchRef.current?.focus());
  }

  return <section className="mb-5 rounded-xl bg-stone-100 p-4">
    <h3 className="font-serif text-xl font-bold">Thêm món vào đơn nháp #{order.sequence_number}</h3>
    <div className="relative mt-3 max-w-2xl">
      <div className="flex items-center gap-2 rounded-lg bg-white px-3 ring-1 ring-stone-300 focus-within:ring-2 focus-within:ring-coffee">
        <MagnifyingGlass className="shrink-0 text-stone-500" />
        <input
          ref={searchRef}
          className="w-full bg-transparent py-3 outline-none"
          role="combobox"
          aria-label="Tìm sản phẩm theo tên"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-activedescendant={open && activeIndex >= 0 ? `${listboxId}-${results[activeIndex]?.id}` : undefined}
          placeholder="Tìm sản phẩm theo tên..."
          value={query}
          disabled={disabled}
          onChange={(event) => { setQuery(event.target.value); setOpen(Boolean(event.target.value.trim())); }}
          onFocus={() => query.trim() && setOpen(true)}
          onKeyDown={handleKeys}
        />
      </div>
      {open && <div id={listboxId} role="listbox" aria-label="Kết quả tìm sản phẩm" className="absolute z-20 mt-2 max-h-72 w-full overflow-auto rounded-xl border border-stone-200 bg-white p-2 shadow-xl">
        {loading ? <Loading label="Đang tìm sản phẩm" /> : searchError ? <p role="alert" className="p-3 text-red-700">{searchError}</p> : results.length === 0 ? <p className="p-3 text-stone-500">Không tìm thấy sản phẩm đang bán.</p> : results.map((product, index) => <button
          id={`${listboxId}-${product.id}`}
          key={product.id}
          type="button"
          role="option"
          aria-selected={index === activeIndex}
          className={`flex w-full items-center justify-between rounded-lg p-3 text-left ${index === activeIndex ? "bg-amber-50" : "hover:bg-stone-50"}`}
          onMouseDown={(event) => event.preventDefault()}
          onMouseEnter={() => setActiveIndex(index)}
          onClick={() => choose(product)}
        ><span><strong className="block">{product.name}</strong><small className="text-stone-500">{product.category?.name ?? "Chưa phân loại"}</small></span><b className="text-coffee">{money(product.base_price)}</b></button>)}
      </div>}
    </div>
    {selectedProduct && <ProductConfigurationDialog
      product={selectedProduct}
      order={order}
      close={() => { setSelectedProduct(null); requestAnimationFrame(() => searchRef.current?.focus()); }}
      added={async (priceChanged) => { await added(priceChanged); finish(); }}
    />}
  </section>;
}

function ProductConfigurationDialog({ product, order, close, added }: { product: Product; order: SessionOrder; close: () => void; added: (priceChanged: boolean) => Promise<void> }) {
  const sizes = product.variants.filter((variant) => variant.is_active && !isAutomaticVariant(product, variant));
  const defaultVariant = product.variants.find((variant) => variant.is_active && isAutomaticVariant(product, variant));
  const [sizeId, setSizeId] = useState(sizes.length === 1 ? String(sizes[0].id) : "");
  const [toppingIds, setToppingIds] = useState<number[]>([]);
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [requestKey] = useState(() => idempotencyKey(`order-item-${order.id}`));
  const closeRef = useRef<HTMLButtonElement>(null);
  const toppings = product.toppings.filter((topping) => topping.is_active);
  const selectedVariant = sizes.length > 0
    ? sizes.find((variant) => variant.id === Number(sizeId))
    : defaultVariant;
  const basePrice = Number(product.base_price);
  const sizePrice = Number(selectedVariant?.price ?? 0);
  const toppingPrice = toppings
    .filter((topping) => toppingIds.includes(topping.id))
    .reduce((total, topping) => total + Number(topping.price), 0);
  const unitPrice = basePrice + sizePrice + toppingPrice;
  const lineTotal = unitPrice * quantity;

  useEffect(() => { closeRef.current?.focus(); }, []);

  async function addToOrder() {
    if (!selectedVariant || (sizes.length > 0 && !sizeId)) {
      setError("Vui lòng chọn size hợp lệ.");
      return;
    }
    setAdding(true);
    setError("");
    try {
      const payload: {
        product_id: number;
        variant_id?: number;
        topping_ids: number[];
        quantity: number;
      } = {
        product_id: product.id,
        topping_ids: toppingIds,
        quantity,
      };
      if (sizes.length > 0) payload.variant_id = selectedVariant.id;
      const response = await request<SessionOrder>(`/orders/${order.id}/items`, {
        method: "POST",
        headers: { "Idempotency-Key": requestKey },
        body: JSON.stringify(payload),
      });
      const authoritativeDelta = Number(response.total_amount) - Number(order.total_amount);
      const priceChanged = Math.abs(authoritativeDelta - lineTotal) > 0.001;
      await added(priceChanged);
    } catch (reason) {
      setError(addItemError(reason));
    } finally {
      setAdding(false);
    }
  }

  return <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !adding && close()} onKeyDown={(event) => { if (event.key === "Escape" && !adding) close(); }}>
    <div className="dialog max-w-2xl" role="dialog" aria-modal="true" aria-label={`Cấu hình ${product.name}`}>
      <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-bold uppercase text-coffee">{product.category?.name}</p><h2 className="font-serif text-2xl font-bold">{product.name}</h2><p className="mt-1 text-stone-600">Giá cơ bản: {money(product.base_price)}</p></div><button ref={closeRef} type="button" className="btn" aria-label="Đóng" disabled={adding} onClick={close}><X /></button></div>
      <div className="mt-5 space-y-5">
        {sizes.length > 0 && <fieldset><legend className="label">Size</legend><div className="grid gap-2 sm:grid-cols-2">{sizes.map((size) => <label key={size.id} className={`cursor-pointer rounded-lg border p-3 ${size.id === Number(sizeId) ? "border-coffee bg-amber-50" : "border-stone-200"}`}><input className="mr-2" type="radio" name="size" value={size.id} checked={size.id === Number(sizeId)} onChange={() => setSizeId(String(size.id))} />{size.name}<b className="float-right">+{money(size.price)}</b></label>)}</div></fieldset>}
        {toppings.length > 0 && <fieldset><legend className="label">Topping</legend><div className="grid gap-2 sm:grid-cols-2">{toppings.map((topping) => <label key={topping.id} className={`cursor-pointer rounded-lg border p-3 ${toppingIds.includes(topping.id) ? "border-coffee bg-amber-50" : "border-stone-200"}`}><input className="mr-2" type="checkbox" checked={toppingIds.includes(topping.id)} onChange={(event) => setToppingIds((current) => event.target.checked ? [...current, topping.id] : current.filter((id) => id !== topping.id))} />{topping.name}<b className="float-right">+{money(topping.price)}</b></label>)}</div></fieldset>}
        <div><span className="label">Số lượng</span><div className="flex w-fit items-center gap-2"><Button type="button" aria-label="Giảm số lượng" disabled={quantity <= 1 || adding} onClick={() => setQuantity((value) => Math.max(1, value - 1))}><Minus /></Button><Input className="w-20 text-center" aria-label="Số lượng" type="number" min="1" max="100" value={quantity} readOnly /><Button type="button" aria-label="Tăng số lượng" disabled={quantity >= 100 || adding} onClick={() => setQuantity((value) => Math.min(100, value + 1))}><Plus /></Button></div></div>
        <div className="rounded-xl bg-stone-100 p-4"><div className="flex justify-between"><span>Đơn giá tạm tính</span><b>{money(unitPrice)}</b></div><div className="mt-2 flex justify-between text-xl"><strong>Thành tiền</strong><strong className="text-coffee">{money(lineTotal)}</strong></div></div>
      </div>
      {error && <p role="alert" className="mt-4 text-red-700">{error}</p>}
      <div className="mt-6 flex justify-end gap-2"><Button type="button" disabled={adding} onClick={close}>Hủy</Button><Button type="button" className="btn-primary" disabled={adding || !selectedVariant || (sizes.length > 0 && !sizeId)} onClick={() => void addToOrder()}>{adding ? "Đang thêm..." : `Thêm vào đơn · ${money(lineTotal)}`}</Button></div>
    </div>
  </div>;
}

function normalizeProduct(product: Product): Product {
  const basePrice = Number(product.base_price);
  if (!Number.isFinite(basePrice)) throw new Error(`API thiếu giá hợp lệ cho ${product.name}`);
  return {
    ...product,
    variants: Array.isArray(product.variants) ? product.variants : [],
    toppings: Array.isArray(product.toppings) ? product.toppings : [],
  };
}

function isAutomaticVariant(product: Product, variant: Variant): boolean {
  return variant.sku === `AUTO-${product.id}`;
}

function addItemError(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 422) return `Lựa chọn món chưa hợp lệ: ${reason.message}`;
    if (reason.code === "order_not_editable") return "Đơn đã được xác nhận và không thể thêm món.";
    if (reason.status === 409) return `Không thể thêm món: ${reason.message}`;
  }
  return reason instanceof Error ? reason.message : "Không thể thêm món vào đơn";
}
