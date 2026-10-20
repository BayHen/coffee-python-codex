import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { MagnifyingGlass, PencilSimple, Plus, Power } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { Button, Empty, Input, Loading, PageHeader, Panel, StatusBadge } from "../components/ui";
import { request } from "../lib/api";
import type { Category, Page, Product, Topping, Variant } from "../types";
import { money } from "../types";

type Editor =
  | { kind: "category" }
  | { kind: "product"; product?: Product }
  | { kind: "size"; product: Product; size?: Variant }
  | { kind: "topping"; product: Product; topping?: Topping }
  | null;

export function ProductsPage() {
  const { canManage } = useAuth();
  const [products, setProducts] = useState<Page<Product> | null>(null);
  const [categories, setCategories] = useState<Page<Category> | null>(null);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [editor, setEditor] = useState<Editor>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try {
      const query = new URLSearchParams({ page_size: "100" });
      if (search) query.set("search", search);
      if (categoryId) query.set("category_id", categoryId);
      const [p, c] = await Promise.all([
        request<Page<Product>>(`/products?${query}`),
        request<Page<Category>>("/categories?page_size=100"),
      ]);
      setProducts({
        ...p,
        items: Array.isArray(p.items)
          ? p.items.map((product) => ({
              ...product,
              base_price: requirePrice(product.base_price, product.name),
              variants: Array.isArray(product.variants) ? product.variants : [],
              toppings: Array.isArray(product.toppings) ? product.toppings : [],
            }))
          : [],
      });
      setCategories({ ...c, items: Array.isArray(c.items) ? c.items : [] });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được sản phẩm"); }
  }, [categoryId, search]);
  useEffect(() => { void load(); }, [load]);
  async function deactivate(path: string) {
    if (!confirm("Ngừng bán mục này? Lịch sử đơn hàng vẫn được giữ.")) return;
    try { await request<void>(path, { method: "DELETE" }); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Không thể cập nhật"); }
  }
  return <><PageHeader title="Products" description="Quản lý danh mục, giá cơ bản, size và topping. Gọi món được thực hiện tại từng bàn." action={canManage && <div className="flex gap-2"><Button onClick={() => setEditor({ kind: "category" })}>Danh mục</Button><Button className="btn-primary" onClick={() => setEditor({ kind: "product" })}><Plus />Sản phẩm</Button></div>} />
    <Panel className="mb-4 grid gap-3 p-3 sm:grid-cols-[1fr_15rem]"><div className="flex items-center gap-2"><MagnifyingGlass className="ml-2 text-stone-500" /><Input aria-label="Tìm sản phẩm" value={search} onChange={(event) => setSearch(event.target.value)} /></div><select className="field" aria-label="Lọc danh mục" value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">Tất cả danh mục</option>{categories?.items.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></Panel>
    {error && <div role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}
    {!products ? <Panel><Loading /></Panel> : products.items.length === 0 ? <Panel><Empty>Không tìm thấy sản phẩm.</Empty></Panel> : <div className="grid gap-4 xl:grid-cols-2">{products.items.map((product) => <Panel key={product.id} className="overflow-hidden"><div className="flex items-start justify-between gap-4 p-5"><div><span className="text-xs font-bold uppercase text-coffee">{product.category?.name ?? "Chưa phân loại"}</span><h2 className="font-serif text-2xl font-bold">{product.name}</h2><strong className="mt-2 block">Giá cơ bản: {money(product.base_price)}</strong><StatusBadge status={product.is_active ? "active" : "inactive"} /></div>{canManage && <div className="flex gap-1"><Button aria-label={`Sửa ${product.name}`} onClick={() => setEditor({ kind: "product", product })}><PencilSimple /></Button>{product.is_active && <Button aria-label={`Ngừng bán ${product.name}`} onClick={() => void deactivate(`/products/${product.id}`)}><Power /></Button>}</div>}</div>
      <OptionList title="Size · giá upsize" add={() => setEditor({ kind: "size", product })}>{product.variants.map((size) => <div key={size.id} className="flex items-center justify-between py-2"><span><b>{size.name}</b> <small>{size.sku}</small></span><span className="flex items-center gap-2">+{money(size.price)}{!size.is_active && <StatusBadge status="inactive" />}{canManage && <Button aria-label={`Sửa size ${size.name}`} onClick={() => setEditor({ kind: "size", product, size })}><PencilSimple /></Button>}</span></div>)}</OptionList>
      <OptionList title="Topping" add={() => setEditor({ kind: "topping", product })}>{product.toppings.map((topping) => <div key={topping.id} className="flex items-center justify-between py-2"><b>{topping.name}</b><span className="flex items-center gap-2">+{money(topping.price)}{!topping.is_active && <StatusBadge status="inactive" />}{canManage && <Button aria-label={`Sửa topping ${topping.name}`} onClick={() => setEditor({ kind: "topping", product, topping })}><PencilSimple /></Button>}</span></div>)}</OptionList>
    </Panel>)}</div>}
    {editor && <EditorDialog editor={editor} categories={categories?.items ?? []} close={() => setEditor(null)} saved={async () => { setEditor(null); await load(); }} />}
  </>;
}

function requirePrice(value: string | undefined, productName: string): string {
  if (value == null || value.trim() === "" || !Number.isFinite(Number(value))) {
    throw new Error(`API thiếu giá cơ bản hợp lệ cho sản phẩm ${productName}`);
  }
  return value;
}

function OptionList({ title, add, children }: { title: string; add: () => void; children: ReactNode }) {
  const { canManage } = useAuth();
  return <div className="border-t border-stone-200 px-5 py-3"><div className="mb-1 flex justify-between"><strong>{title}</strong>{canManage && <button className="text-sm font-bold text-coffee" onClick={add}>+ Thêm</button>}</div>{children}</div>;
}

function EditorDialog({ editor, categories, close, saved }: { editor: NonNullable<Editor>; categories: Category[]; close: () => void; saved: () => Promise<void> }) {
  const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const [categoryId, setCategoryId] = useState("");
  const [categoryName, setCategoryName] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setError(""); const form = new FormData(event.currentTarget);
    try {
      if (editor.kind === "category") await request(categoryId ? `/categories/${categoryId}` : "/categories", { method: categoryId ? "PATCH" : "POST", body: JSON.stringify({ name: categoryName }) });
      if (editor.kind === "product") await request(editor.product ? `/products/${editor.product.id}` : "/products", { method: editor.product ? "PATCH" : "POST", body: JSON.stringify({ name: form.get("name"), category_id: Number(form.get("category_id")), base_price: form.get("base_price"), is_active: form.get("is_active") === "on" }) });
      if (editor.kind === "size") await request(editor.size ? `/products/${editor.product.id}/variants/${editor.size.id}` : `/products/${editor.product.id}/variants`, { method: editor.size ? "PATCH" : "POST", body: JSON.stringify({ sku: form.get("sku"), name: form.get("name"), price: form.get("price"), is_active: form.get("is_active") === "on" }) });
      if (editor.kind === "topping") await request(editor.topping ? `/products/${editor.product.id}/toppings/${editor.topping.id}` : `/products/${editor.product.id}/toppings`, { method: editor.topping ? "PATCH" : "POST", body: JSON.stringify({ name: form.get("name"), price: form.get("price"), is_active: form.get("is_active") === "on" }) });
      await saved();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Không thể lưu"); } finally { setSaving(false); }
  }
  return <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && close()}><form className="dialog" role="dialog" aria-modal="true" aria-label="Chỉnh sửa Products" onSubmit={submit}><h2 className="font-serif text-2xl font-bold">Chỉnh sửa Products</h2><div className="mt-5 space-y-4">
    {editor.kind === "category" && <><label><span className="label">Danh mục</span><select className="field" value={categoryId} onChange={(event) => { const id = event.target.value; setCategoryId(id); setCategoryName(categories.find((item) => item.id === Number(id))?.name ?? ""); }}><option value="">+ Danh mục mới</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label><span className="label">Tên danh mục</span><Input value={categoryName} onChange={(event) => setCategoryName(event.target.value)} required /></label>{categoryId && <Button type="button" className="btn-danger" onClick={() => { if (confirm("Xóa danh mục này? Chỉ danh mục chưa có sản phẩm mới được xóa.")) void request(`/categories/${categoryId}`, { method: "DELETE" }).then(saved).catch((reason) => setError(reason instanceof Error ? reason.message : "Không thể xóa")); }}>Xóa danh mục</Button>}</>}
    {editor.kind === "product" && <><label><span className="label">Tên sản phẩm</span><Input name="name" defaultValue={editor.product?.name} required /></label><label><span className="label">Danh mục</span><select className="field" name="category_id" defaultValue={editor.product?.category_id} required>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label><span className="label">Giá cơ bản (VND, ví dụ 25000)</span><Input name="base_price" type="number" min="0" step="1000" defaultValue={editor.product?.base_price} required /></label></>}
    {editor.kind === "size" && <><label><span className="label">SKU</span><Input name="sku" defaultValue={editor.size?.sku} required /></label><label><span className="label">Tên size</span><Input name="name" defaultValue={editor.size?.name} required /></label></>}
    {(editor.kind === "size" || editor.kind === "topping") && <><label><span className="label">{editor.kind === "size" ? "Giá upsize (VND)" : "Giá topping (VND)"}</span><Input name="price" type="number" min="0" step="1000" defaultValue={editor.kind === "size" ? editor.size?.price : editor.topping?.price} required /></label><label className="flex gap-2"><input name="is_active" type="checkbox" defaultChecked={(editor.kind === "size" ? editor.size?.is_active : editor.topping?.is_active) ?? true} /> Đang bán</label></>}
    {editor.kind === "topping" && <label><span className="label">Tên topping</span><Input name="name" defaultValue={editor.topping?.name} required /></label>}
    {editor.kind === "product" && <label className="flex gap-2"><input name="is_active" type="checkbox" defaultChecked={editor.product?.is_active ?? true} /> Đang bán</label>}
  </div>{error && <p role="alert" className="mt-4 text-red-700">{error}</p>}<div className="mt-6 flex justify-end gap-2"><Button type="button" onClick={close}>Hủy</Button><Button className="btn-primary" disabled={saving}>Lưu</Button></div></form></div>;
}
