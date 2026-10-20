import { useCallback, useEffect, useState, type FormEvent } from "react";
import { MagnifyingGlass, PencilSimple, Plus, Power } from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import { Button, Empty, ErrorState, Input, Loading, PageHeader, Panel, StatusBadge } from "../components/ui";
import { request } from "../lib/api";
import type { Category, Page, Product, Variant } from "../types";
import { money } from "../types";

type Editor = { kind: "category" | "product" | "variant"; product?: Product; variant?: Variant } | null;
export function ProductsPage() {
  const { canManage } = useAuth();
  const [products, setProducts] = useState<Page<Product> | null>(null);
  const [categories, setCategories] = useState<Page<Category> | null>(null);
  const [search, setSearch] = useState("");
  const [editor, setEditor] = useState<Editor>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try {
      const query = new URLSearchParams({ page_size: "100" });
      if (search) query.set("search", search);
      const [p, c] = await Promise.all([request<Page<Product>>(`/products?${query}`), request<Page<Category>>("/categories?page_size=100")]);
      setProducts(p); setCategories(c);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Không tải được sản phẩm"); }
  }, [search]);
  useEffect(() => { void load(); }, [load]);
  async function deactivate(path: string) { if (!confirm("Ngừng bán mục này? Lịch sử đơn hàng vẫn được giữ.")) return; await request<void>(path, { method: "DELETE" }); await load(); }
  return <><PageHeader title="Sản phẩm" description="Quản lý danh mục, món bán và các biến thể giá." action={canManage && <div className="flex gap-2"><Button onClick={() => setEditor({ kind: "category" })}>Danh mục</Button><Button className="btn-primary" onClick={() => setEditor({ kind: "product" })}><Plus size={18} />Sản phẩm</Button></div>} />
    <Panel className="mb-4 flex items-center gap-3 p-3"><MagnifyingGlass className="ml-2 text-stone-500" /><Input aria-label="Tìm sản phẩm" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Tên sản phẩm..." /></Panel>
    {error ? <Panel><ErrorState message={error} retry={() => void load()} /></Panel> : !products ? <Panel><Loading /></Panel> : products.items.length === 0 ? <Panel><Empty>Không tìm thấy sản phẩm.</Empty></Panel> : <div className="grid gap-4 xl:grid-cols-2">{products.items.map((product) => <Panel key={product.id} className="overflow-hidden"><div className="flex items-start justify-between gap-4 p-5"><div><span className="text-xs font-bold uppercase tracking-wide text-coffee">{product.category.name}</span><h2 className="mt-1 font-serif text-2xl font-bold">{product.name}</h2><div className="mt-2"><StatusBadge status={product.is_active ? "active" : "inactive"} /></div></div>{canManage && <div className="flex gap-1"><Button aria-label={`Sửa ${product.name}`} onClick={() => setEditor({ kind: "product", product })}><PencilSimple /></Button>{product.is_active && <Button aria-label={`Ngừng bán ${product.name}`} onClick={() => void deactivate(`/products/${product.id}`)}><Power /></Button>}</div>}</div>
      <div className="border-t border-stone-200 px-5 py-3"><div className="mb-2 flex justify-between"><strong className="text-sm">Biến thể</strong>{canManage && <button className="text-sm font-bold text-coffee" onClick={() => setEditor({ kind: "variant", product })}>+ Thêm</button>}</div>{product.variants.length === 0 ? <p className="py-3 text-sm text-stone-500">Chưa có biến thể.</p> : product.variants.map((variant) => <div key={variant.id} className="flex items-center justify-between gap-3 py-2"><div><span className="font-bold">{variant.name}</span><span className="ml-2 text-xs text-stone-500">{variant.sku}</span></div><div className="flex items-center gap-2"><span>{money(variant.price)}</span>{!variant.is_active && <StatusBadge status="inactive" />}{canManage && <Button aria-label={`Sửa ${variant.name}`} onClick={() => setEditor({ kind: "variant", product, variant })}><PencilSimple /></Button>}</div></div>)}</div>
    </Panel>)}</div>}
    {editor && <CatalogDialog editor={editor} categories={categories?.items ?? []} close={() => setEditor(null)} saved={async () => { setEditor(null); await load(); }} />}
  </>;
}

function CatalogDialog({ editor, categories, close, saved }: { editor: NonNullable<Editor>; categories: Category[]; close: () => void; saved: () => Promise<void> }) {
  const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setError(""); const f = new FormData(event.currentTarget);
    try {
      if (editor.kind === "category") await request("/categories", { method: "POST", body: JSON.stringify({ name: f.get("name") }) });
      if (editor.kind === "product") {
        const body = { name: f.get("name"), category_id: Number(f.get("category_id")), is_active: f.get("is_active") === "on" };
        await request(editor.product ? `/products/${editor.product.id}` : "/products", { method: editor.product ? "PATCH" : "POST", body: JSON.stringify(body) });
      }
      if (editor.kind === "variant" && editor.product) {
        const body = { sku: f.get("sku"), name: f.get("name"), price: f.get("price"), is_active: f.get("is_active") === "on" };
        await request(editor.variant ? `/products/${editor.product.id}/variants/${editor.variant.id}` : `/products/${editor.product.id}/variants`, { method: editor.variant ? "PATCH" : "POST", body: JSON.stringify(body) });
      }
      await saved();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Không thể lưu"); } finally { setSaving(false); }
  }
  const title = editor.kind === "category" ? "Thêm danh mục" : editor.kind === "product" ? `${editor.product ? "Sửa" : "Thêm"} sản phẩm` : `${editor.variant ? "Sửa" : "Thêm"} biến thể`;
  return <div className="dialog-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && close()}><form className="dialog" role="dialog" aria-modal="true" aria-label={title} onSubmit={submit}><h2 className="font-serif text-2xl font-bold">{title}</h2><div className="mt-5 space-y-4">
    {editor.kind === "category" && <label><span className="label">Tên danh mục</span><Input name="name" required maxLength={100} autoFocus /></label>}
    {editor.kind === "product" && <><label><span className="label">Tên sản phẩm</span><Input name="name" defaultValue={editor.product?.name} required autoFocus /></label><label><span className="label">Danh mục</span><select className="field" name="category_id" defaultValue={editor.product?.category_id} required>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label><label className="flex items-center gap-2"><input type="checkbox" name="is_active" defaultChecked={editor.product?.is_active ?? true} /> Đang bán</label></>}
    {editor.kind === "variant" && <><label><span className="label">SKU</span><Input name="sku" defaultValue={editor.variant?.sku} pattern="[A-Za-z0-9][A-Za-z0-9._-]*" required autoFocus /></label><label><span className="label">Tên biến thể</span><Input name="name" defaultValue={editor.variant?.name} required /></label><label><span className="label">Giá</span><Input name="price" type="number" min="0" step="0.01" defaultValue={editor.variant?.price} required /></label><label className="flex items-center gap-2"><input type="checkbox" name="is_active" defaultChecked={editor.variant?.is_active ?? true} /> Đang bán</label></>}
  </div>{error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}<div className="mt-6 flex justify-end gap-2"><Button type="button" onClick={close}>Hủy</Button><Button className="btn-primary" disabled={saving}>{saving ? "Đang lưu..." : "Lưu"}</Button></div></form></div>;
}
