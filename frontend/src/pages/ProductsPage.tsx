import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  MagnifyingGlass,
  PencilSimple,
  Plus,
  Power,
} from "@phosphor-icons/react";
import { useAuth } from "../auth/AuthContext";
import {
  Button,
  Empty,
  Input,
  Loading,
  PageHeader,
  Panel,
  StatusBadge,
} from "../components/ui";
import { ApiError, request } from "../lib/api";
import type {
  Category,
  CategoryDeletionOptions,
  CategoryReassignDeleteResult,
  CreateProductRequest,
  CreateVariantRequest,
  Page,
  Product,
  Topping,
  UpdateProductRequest,
  UpdateVariantRequest,
  Variant,
} from "../types";
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
  const [success, setSuccess] = useState("");
  const load = useCallback(
    async (categoryOverride?: string) => {
      setError("");
      try {
        const query = new URLSearchParams({ page_size: "100" });
        if (search) query.set("search", search);
        const activeCategoryId = categoryOverride ?? categoryId;
        if (activeCategoryId) query.set("category_id", activeCategoryId);
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
                variants: Array.isArray(product.variants)
                  ? product.variants
                  : [],
                toppings: Array.isArray(product.toppings)
                  ? product.toppings
                  : [],
              }))
            : [],
        });
        setCategories({ ...c, items: Array.isArray(c.items) ? c.items : [] });
      } catch (reason) {
        setError(
          reason instanceof Error ? reason.message : "Không tải được sản phẩm",
        );
      }
    },
    [categoryId, search],
  );
  useEffect(() => {
    void load();
  }, [load]);
  async function deactivate(path: string) {
    if (!confirm("Ngừng bán mục này? Lịch sử đơn hàng vẫn được giữ.")) return;
    try {
      await request<void>(path, { method: "DELETE" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể cập nhật");
    }
  }
  return (
    <>
      <PageHeader
        title="Products"
        description="Quản lý danh mục, giá cơ bản, size và topping. Gọi món được thực hiện tại từng bàn."
        action={
          canManage && (
            <div className="flex gap-2">
              <Button onClick={() => setEditor({ kind: "category" })}>
                Danh mục
              </Button>
              <Button
                className="btn-primary"
                onClick={() => setEditor({ kind: "product" })}
              >
                <Plus />
                Sản phẩm
              </Button>
            </div>
          )
        }
      />
      <Panel className="mb-4 grid gap-3 p-3 sm:grid-cols-[1fr_15rem]">
        <div className="flex items-center gap-2">
          <MagnifyingGlass className="ml-2 text-stone-500" />
          <Input
            aria-label="Tìm sản phẩm"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <select
          className="field"
          aria-label="Lọc danh mục"
          value={categoryId}
          onChange={(event) => setCategoryId(event.target.value)}
        >
          <option value="">Tất cả danh mục</option>
          {categories?.items.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
      </Panel>
      {success && (
        <div
          role="status"
          className="mb-4 rounded-lg bg-green-50 p-3 text-green-800"
        >
          {success}
        </div>
      )}
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-lg bg-red-50 p-3 text-red-700"
        >
          {error}
        </div>
      )}
      {!products ? (
        <Panel>
          <Loading />
        </Panel>
      ) : products.items.length === 0 ? (
        <Panel>
          <Empty>Không tìm thấy sản phẩm.</Empty>
        </Panel>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {products.items.map((product) => (
            <Panel key={product.id} className="overflow-hidden">
              <div className="flex items-start justify-between gap-4 p-5">
                <div>
                  <span className="text-xs font-bold uppercase text-coffee">
                    {product.category?.name ?? "Chưa phân loại"}
                  </span>
                  <h2 className="font-serif text-2xl font-bold">
                    {product.name}
                  </h2>
                  <strong className="mt-2 block">
                    Giá cơ bản: {money(product.base_price)}
                  </strong>
                  <StatusBadge
                    status={product.is_active ? "active" : "inactive"}
                  />
                </div>
                {canManage && (
                  <div className="flex gap-1">
                    <Button
                      aria-label={`Sửa ${product.name}`}
                      onClick={() => setEditor({ kind: "product", product })}
                    >
                      <PencilSimple />
                    </Button>
                    {product.is_active && (
                      <Button
                        aria-label={`Ngừng bán ${product.name}`}
                        onClick={() =>
                          void deactivate(`/products/${product.id}`)
                        }
                      >
                        <Power />
                      </Button>
                    )}
                  </div>
                )}
              </div>
              <OptionList
                title="Size · giá upsize"
                add={() => setEditor({ kind: "size", product })}
              >
                {product.variants.map((size) => (
                  <div
                    key={size.id}
                    className="flex items-center justify-between py-2"
                  >
                    <span>
                      <b>{size.name}</b>
                    </span>
                    <span className="flex items-center gap-2">
                      +{money(size.price)}
                      {!size.is_active && <StatusBadge status="inactive" />}
                      {canManage && (
                        <Button
                          aria-label={`Sửa size ${size.name}`}
                          onClick={() =>
                            setEditor({ kind: "size", product, size })
                          }
                        >
                          <PencilSimple />
                        </Button>
                      )}
                    </span>
                  </div>
                ))}
              </OptionList>
              <OptionList
                title="Topping"
                add={() => setEditor({ kind: "topping", product })}
              >
                {product.toppings.map((topping) => (
                  <div
                    key={topping.id}
                    className="flex items-center justify-between py-2"
                  >
                    <b>{topping.name}</b>
                    <span className="flex items-center gap-2">
                      +{money(topping.price)}
                      {!topping.is_active && <StatusBadge status="inactive" />}
                      {canManage && (
                        <Button
                          aria-label={`Sửa topping ${topping.name}`}
                          onClick={() =>
                            setEditor({ kind: "topping", product, topping })
                          }
                        >
                          <PencilSimple />
                        </Button>
                      )}
                    </span>
                  </div>
                ))}
              </OptionList>
            </Panel>
          ))}
        </div>
      )}
      {editor && (
        <EditorDialog
          editor={editor}
          categories={categories?.items ?? []}
          close={() => setEditor(null)}
          saved={async (message, deletedCategoryId) => {
            setEditor(null);
            setSuccess(message);
            const resetFilter =
              deletedCategoryId != null &&
              categoryId === String(deletedCategoryId);
            if (resetFilter) setCategoryId("");
            await load(resetFilter ? "" : undefined);
          }}
        />
      )}
    </>
  );
}

function requirePrice(value: string | undefined, productName: string): string {
  if (value == null || value.trim() === "" || !Number.isFinite(Number(value))) {
    throw new Error(`API thiếu giá cơ bản hợp lệ cho sản phẩm ${productName}`);
  }
  return value;
}

function OptionList({
  title,
  add,
  children,
}: {
  title: string;
  add: () => void;
  children: ReactNode;
}) {
  const { canManage } = useAuth();
  return (
    <div className="border-t border-stone-200 px-5 py-3">
      <div className="mb-1 flex justify-between">
        <strong>{title}</strong>
        {canManage && (
          <button className="text-sm font-bold text-coffee" onClick={add}>
            + Thêm
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

function EditorDialog({
  editor,
  categories,
  close,
  saved,
}: {
  editor: NonNullable<Editor>;
  categories: Category[];
  close: () => void;
  saved: (message: string, deletedCategoryId?: number) => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [categoryId, setCategoryId] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [deletionOptions, setDeletionOptions] =
    useState<CategoryDeletionOptions | null>(null);
  const [replacementCategoryId, setReplacementCategoryId] = useState("");

  async function prepareCategoryDeletion() {
    if (!categoryId) return;
    setSaving(true);
    setError("");
    try {
      const options = await request<CategoryDeletionOptions>(
        `/categories/${categoryId}/deletion-options`,
      );
      setDeletionOptions(options);
      setReplacementCategoryId(
        options.preferred_replacement_category_id?.toString() ?? "",
      );
    } catch (reason) {
      setError(categoryDeleteError(reason));
    } finally {
      setSaving(false);
    }
  }

  async function confirmCategoryDeletion() {
    if (!deletionOptions) return;
    setSaving(true);
    setError("");
    try {
      if (deletionOptions.linked_product_count === 0) {
        await request<void>(`/categories/${deletionOptions.category.id}`, {
          method: "DELETE",
        });
        await saved(
          `Đã xóa danh mục ${deletionOptions.category.name}.`,
          deletionOptions.category.id,
        );
        return;
      }
      if (!replacementCategoryId) {
        setError("Vui lòng chọn danh mục thay thế trước khi tiếp tục.");
        return;
      }
      const result = await request<CategoryReassignDeleteResult>(
        `/categories/${deletionOptions.category.id}/reassign-and-delete`,
        {
          method: "POST",
          body: JSON.stringify({
            replacement_category_id: Number(replacementCategoryId),
          }),
        },
      );
      const replacement = deletionOptions.replacement_categories.find(
        (item) => item.id === result.replacement_category_id,
      );
      await saved(
        `Đã chuyển ${result.reassigned_product_count} sản phẩm sang ${replacement?.name ?? "danh mục mới"} và xóa ${deletionOptions.category.name}.`,
        deletionOptions.category.id,
      );
    } catch (reason) {
      setError(categoryDeleteError(reason));
    } finally {
      setSaving(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      if (editor.kind === "category")
        await request(
          categoryId ? `/categories/${categoryId}` : "/categories",
          {
            method: categoryId ? "PATCH" : "POST",
            body: JSON.stringify({ name: categoryName }),
          },
        );
      if (editor.kind === "product") {
        const payload = {
          name: String(form.get("name")),
          category_id: Number(form.get("category_id")),
          base_price: String(form.get("base_price")),
          is_active: form.get("is_active") === "on",
        } satisfies CreateProductRequest | UpdateProductRequest;
        await request<Product>(
          editor.product ? `/products/${editor.product.id}` : "/products",
          {
            method: editor.product ? "PATCH" : "POST",
            body: JSON.stringify(payload),
          },
        );
      }
      if (editor.kind === "size") {
        const payload = {
          name: String(form.get("name")),
          price: String(form.get("price")),
          is_active: form.get("is_active") === "on",
        } satisfies CreateVariantRequest | UpdateVariantRequest;
        await request<Variant>(
          editor.size
            ? `/products/${editor.product.id}/variants/${editor.size.id}`
            : `/products/${editor.product.id}/variants`,
          {
            method: editor.size ? "PATCH" : "POST",
            body: JSON.stringify(payload),
          },
        );
      }
      if (editor.kind === "topping")
        await request(
          editor.topping
            ? `/products/${editor.product.id}/toppings/${editor.topping.id}`
            : `/products/${editor.product.id}/toppings`,
          {
            method: editor.topping ? "PATCH" : "POST",
            body: JSON.stringify({
              name: form.get("name"),
              price: form.get("price"),
              is_active: form.get("is_active") === "on",
            }),
          },
        );
      await saved("Đã lưu thay đổi.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể lưu");
    } finally {
      setSaving(false);
    }
  }
  const deleting = deletionOptions !== null;
  const dialogTitle =
    editor.kind === "size"
      ? editor.size
        ? "Chỉnh sửa size"
        : "Thêm size"
      : "Chỉnh sửa Products";
  return (
    <div
      className="dialog-backdrop"
      role="presentation"
      onMouseDown={(event) =>
        event.target === event.currentTarget && !saving && close()
      }
    >
      <form
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={dialogTitle}
        onSubmit={submit}
      >
        <h2 className="font-serif text-2xl font-bold">
          {deleting
            ? `Xóa danh mục ${deletionOptions.category.name}`
            : dialogTitle}
        </h2>
        <div className="mt-5 space-y-4">
          {editor.kind === "category" && !deleting && (
            <>
              <label>
                <span className="label">Danh mục</span>
                <select
                  className="field"
                  value={categoryId}
                  onChange={(event) => {
                    const id = event.target.value;
                    setCategoryId(id);
                    setCategoryName(
                      categories.find((item) => item.id === Number(id))?.name ??
                        "",
                    );
                    setDeletionOptions(null);
                    setError("");
                  }}
                >
                  <option value="">+ Danh mục mới</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span className="label">Tên danh mục</span>
                <Input
                  value={categoryName}
                  onChange={(event) => setCategoryName(event.target.value)}
                  required
                />
              </label>
              {categoryId && (
                <Button
                  type="button"
                  className="btn-danger"
                  disabled={saving}
                  onClick={() => void prepareCategoryDeletion()}
                >
                  Xóa danh mục
                </Button>
              )}
            </>
          )}
          {editor.kind === "category" &&
            deleting &&
            deletionOptions.linked_product_count === 0 && (
              <>
                <p>Danh mục này không có sản phẩm. Bạn có chắc muốn xóa?</p>
                <dl className="rounded-lg bg-stone-50 p-3">
                  <dt className="text-sm text-stone-500">Danh mục</dt>
                  <dd className="font-bold">{deletionOptions.category.name}</dd>
                </dl>
              </>
            )}
          {editor.kind === "category" &&
            deleting &&
            deletionOptions.linked_product_count > 0 && (
              <>
                <p>
                  Danh mục này đang chứa sản phẩm. Vui lòng chọn danh mục thay
                  thế để chuyển sản phẩm trước khi xóa.
                </p>
                <dl className="grid grid-cols-2 gap-3 rounded-lg bg-stone-50 p-3">
                  <div>
                    <dt className="text-sm text-stone-500">Danh mục</dt>
                    <dd className="font-bold">
                      {deletionOptions.category.name}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm text-stone-500">
                      Sản phẩm liên kết
                    </dt>
                    <dd className="font-bold">
                      {deletionOptions.linked_product_count}
                    </dd>
                  </div>
                </dl>
                {deletionOptions.preferred_replacement_category_id === null && (
                  <p className="rounded-lg bg-amber-50 p-3 text-amber-800">
                    Chưa có danh mục Trà phù hợp. Vui lòng chọn một danh mục
                    thay thế khác.
                  </p>
                )}
                <label>
                  <span className="label">Danh mục thay thế</span>
                  <select
                    className="field"
                    aria-label="Danh mục thay thế"
                    value={replacementCategoryId}
                    onChange={(event) =>
                      setReplacementCategoryId(event.target.value)
                    }
                  >
                    <option value="">Chọn danh mục</option>
                    {deletionOptions.replacement_categories.map((category) => (
                      <option key={category.id} value={category.id}>
                        {category.name}
                      </option>
                    ))}
                  </select>
                </label>
                {deletionOptions.replacement_categories.length === 0 && (
                  <p role="alert" className="text-red-700">
                    Không có danh mục thay thế. Hãy tạo một danh mục khác trước
                    khi xóa.
                  </p>
                )}
                <p className="text-sm text-stone-600">
                  Các sản phẩm sẽ được chuyển sang danh mục mới. Sản phẩm, giá
                  bán và lịch sử đơn hàng không bị xóa.
                </p>
              </>
            )}
          {editor.kind === "product" && (
            <>
              <label>
                <span className="label">Tên sản phẩm</span>
                <Input
                  name="name"
                  defaultValue={editor.product?.name}
                  required
                />
              </label>
              <label>
                <span className="label">Danh mục</span>
                <select
                  className="field"
                  name="category_id"
                  defaultValue={editor.product?.category_id}
                  required
                >
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span className="label">Giá cơ bản (VND, ví dụ 25000)</span>
                <Input
                  name="base_price"
                  type="number"
                  min="0"
                  step="1000"
                  defaultValue={editor.product?.base_price}
                  required
                />
              </label>
            </>
          )}
          {editor.kind === "size" && (
            <>
              <label>
                <span className="label">Tên size</span>
                <Input name="name" defaultValue={editor.size?.name} required />
              </label>
            </>
          )}
          {(editor.kind === "size" || editor.kind === "topping") && (
            <>
              <label>
                <span className="label">
                  {editor.kind === "size"
                    ? "Giá upsize (VND)"
                    : "Giá topping (VND)"}
                </span>
                <Input
                  name="price"
                  type="number"
                  min="0"
                  step="1000"
                  defaultValue={
                    editor.kind === "size"
                      ? editor.size?.price
                      : editor.topping?.price
                  }
                  required
                />
              </label>
              <label className="flex gap-2">
                <input
                  name="is_active"
                  type="checkbox"
                  defaultChecked={
                    (editor.kind === "size"
                      ? editor.size?.is_active
                      : editor.topping?.is_active) ?? true
                  }
                />{" "}
                Đang bán
              </label>
            </>
          )}
          {editor.kind === "topping" && (
            <label>
              <span className="label">Tên topping</span>
              <Input name="name" defaultValue={editor.topping?.name} required />
            </label>
          )}
          {editor.kind === "product" && (
            <label className="flex gap-2">
              <input
                name="is_active"
                type="checkbox"
                defaultChecked={editor.product?.is_active ?? true}
              />{" "}
              Đang bán
            </label>
          )}
        </div>
        {error && (
          <p role="alert" className="mt-4 text-red-700">
            {error}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <Button
            type="button"
            disabled={saving}
            onClick={
              deleting
                ? () => {
                    setDeletionOptions(null);
                    setError("");
                  }
                : close
            }
          >
            Hủy
          </Button>
          {deleting ? (
            <Button
              type="button"
              className="btn-danger"
              disabled={
                saving ||
                (deletionOptions.linked_product_count > 0 &&
                  !replacementCategoryId)
              }
              onClick={() => void confirmCategoryDeletion()}
            >
              {saving
                ? "Đang xử lý..."
                : deletionOptions.linked_product_count > 0
                  ? "Chuyển sản phẩm và xóa danh mục"
                  : "Xác nhận xóa"}
            </Button>
          ) : (
            <Button className="btn-primary" disabled={saving}>
              {saving ? "Đang lưu..." : "Lưu"}
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

function categoryDeleteError(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.code === "category_reassignment_conflict")
      return "Không thể chuyển vì danh mục thay thế đã có sản phẩm trùng tên.";
    if (reason.code === "replacement_category_not_found")
      return "Danh mục thay thế không còn tồn tại. Vui lòng chọn lại.";
    if (reason.code === "replacement_category_must_differ")
      return "Danh mục thay thế phải khác danh mục đang xóa.";
    if (reason.code === "category_not_found")
      return "Danh mục cần xóa không còn tồn tại.";
  }
  return reason instanceof Error ? reason.message : "Không thể xóa danh mục";
}
