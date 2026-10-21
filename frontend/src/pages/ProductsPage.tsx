import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  ArrowCounterClockwise,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  Power,
  Trash,
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
  OptionRemovalResult,
  OptionStatus,
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

type ManagedOption = Variant | Topping;
type OptionAction = {
  kind: "status" | "delete";
  optionKind: "size" | "topping";
  product: Product;
  option: ManagedOption;
  nextActive?: boolean;
};

export function ProductsPage() {
  const { canManage } = useAuth();
  const [products, setProducts] = useState<Page<Product> | null>(null);
  const [categories, setCategories] = useState<Page<Category> | null>(null);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [editor, setEditor] = useState<Editor>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [optionStatus, setOptionStatus] = useState<OptionStatus>("all");
  const [optionAction, setOptionAction] = useState<OptionAction | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState("");
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
  async function confirmOptionAction() {
    if (!optionAction || actionBusy) return;
    setActionBusy(true);
    setError("");
    setActionError("");
    const optionPath = optionAction.optionKind === "size" ? "variants" : "toppings";
    const path = `/products/${optionAction.product.id}/${optionPath}/${optionAction.option.id}`;
    try {
      if (optionAction.kind === "status") {
        await request(path + "/status", {
          method: "PATCH",
          body: JSON.stringify({ is_active: optionAction.nextActive }),
        });
        setSuccess(
          optionAction.nextActive
            ? "Đã kích hoạt lại lựa chọn. ID và SKU được giữ nguyên."
            : "Đã ngừng bán lựa chọn. Lịch sử đơn hàng được giữ nguyên.",
        );
      } else {
        const result = await request<OptionRemovalResult>(path, {
          method: "DELETE",
        });
        setSuccess(
          result.action === "deleted"
            ? "Đã xóa lựa chọn chưa từng được sử dụng."
            : "Lựa chọn đã được sử dụng trong đơn hàng. Hệ thống đã ngừng bán thay vì xóa lịch sử.",
        );
      }
      setOptionAction(null);
      await load();
    } catch (reason) {
      const message = optionActionError(reason);
      setActionError(message);
      if (!(reason instanceof ApiError)) {
        await load();
        setOptionAction(null);
        setError(`${message}. Danh sách đã được tải lại để xác minh trạng thái.`);
      }
    } finally {
      setActionBusy(false);
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
      <div
        className="mb-4 flex flex-wrap items-center gap-2"
        role="group"
        aria-label="Lọc trạng thái size và topping"
      >
        <span className="mr-1 text-sm font-bold text-stone-600">Lựa chọn:</span>
        {(["all", "active", "inactive"] as const).map((status) => (
          <Button
            key={status}
            aria-pressed={optionStatus === status}
            className={optionStatus === status ? "btn-primary" : ""}
            onClick={() => setOptionStatus(status)}
          >
            {status === "all"
              ? "Tất cả"
              : status === "active"
                ? "Đang bán"
                : "Ngừng bán"}
          </Button>
        ))}
        <span className="text-xs text-stone-500">
          Áp dụng cho Size và Topping trên mọi sản phẩm đang hiển thị.
        </span>
      </div>
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
                {product.variants.filter((size) =>
                  optionMatches(size, optionStatus),
                ).length === 0 && (
                  <Empty>Không có size phù hợp bộ lọc.</Empty>
                )}
                {product.variants
                  .filter((size) => optionMatches(size, optionStatus))
                  .map((size) => (
                  <div
                    key={size.id}
                    className="flex items-center justify-between py-2"
                  >
                    <span>
                      <b>{size.name}</b>
                    </span>
                    <span className="flex items-center gap-2">
                      +{money(size.price)}
                      <StatusBadge
                        status={size.is_active ? "active" : "inactive"}
                      />
                      {canManage && (
                        <>
                          <Button
                            aria-label={`Sửa size ${size.name}`}
                            onClick={() =>
                              setEditor({ kind: "size", product, size })
                            }
                          >
                            <PencilSimple />
                          </Button>
                          <Button
                            aria-label={`${size.is_active ? "Ngừng bán" : "Kích hoạt lại"} size ${size.name}`}
                            onClick={() =>
                              setOptionAction({
                                kind: "status",
                                optionKind: "size",
                                product,
                                option: size,
                                nextActive: !size.is_active,
                              })
                            }
                          >
                            {size.is_active ? (
                              <Power />
                            ) : (
                              <ArrowCounterClockwise />
                            )}
                          </Button>
                          <Button
                            aria-label={`Xóa size ${size.name}`}
                            onClick={() =>
                              setOptionAction({
                                kind: "delete",
                                optionKind: "size",
                                product,
                                option: size,
                              })
                            }
                          >
                            <Trash />
                          </Button>
                        </>
                      )}
                    </span>
                  </div>
                  ))}
              </OptionList>
              <OptionList
                title="Topping"
                add={() => setEditor({ kind: "topping", product })}
              >
                {product.toppings.filter((topping) =>
                  optionMatches(topping, optionStatus),
                ).length === 0 && (
                  <Empty>Không có topping phù hợp bộ lọc.</Empty>
                )}
                {product.toppings
                  .filter((topping) => optionMatches(topping, optionStatus))
                  .map((topping) => (
                  <div
                    key={topping.id}
                    className="flex items-center justify-between py-2"
                  >
                    <b>{topping.name}</b>
                    <span className="flex items-center gap-2">
                      +{money(topping.price)}
                      <StatusBadge
                        status={topping.is_active ? "active" : "inactive"}
                      />
                      {canManage && (
                        <>
                          <Button
                            aria-label={`Sửa topping ${topping.name}`}
                            onClick={() =>
                              setEditor({ kind: "topping", product, topping })
                            }
                          >
                            <PencilSimple />
                          </Button>
                          <Button
                            aria-label={`${topping.is_active ? "Ngừng bán" : "Kích hoạt lại"} topping ${topping.name}`}
                            onClick={() =>
                              setOptionAction({
                                kind: "status",
                                optionKind: "topping",
                                product,
                                option: topping,
                                nextActive: !topping.is_active,
                              })
                            }
                          >
                            {topping.is_active ? (
                              <Power />
                            ) : (
                              <ArrowCounterClockwise />
                            )}
                          </Button>
                          <Button
                            aria-label={`Xóa topping ${topping.name}`}
                            onClick={() =>
                              setOptionAction({
                                kind: "delete",
                                optionKind: "topping",
                                product,
                                option: topping,
                              })
                            }
                          >
                            <Trash />
                          </Button>
                        </>
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
      {optionAction && (
        <OptionConfirmationDialog
          action={optionAction}
          busy={actionBusy}
          error={actionError}
          close={() => {
            if (!actionBusy) {
              setActionError("");
              setOptionAction(null);
            }
          }}
          confirm={() => void confirmOptionAction()}
        />
      )}
    </>
  );
}

function optionMatches(
  option: { is_active: boolean },
  status: OptionStatus,
): boolean {
  if (status === "all") return true;
  return option.is_active === (status === "active");
}

function OptionConfirmationDialog({
  action,
  busy,
  error,
  close,
  confirm,
}: {
  action: OptionAction;
  busy: boolean;
  error: string;
  close: () => void;
  confirm: () => void;
}) {
  const label = action.optionKind === "size" ? "Size" : "Topping";
  const title =
    action.kind === "delete"
      ? `Xóa ${label}`
      : action.nextActive
        ? `Kích hoạt lại ${label}`
        : `Ngừng bán ${label}`;
  const message =
    action.kind === "delete"
      ? "Bạn có chắc muốn xóa lựa chọn này? Nếu đã được sử dụng, hệ thống sẽ chỉ ngừng bán để bảo vệ lịch sử."
      : action.nextActive
        ? `Bạn có chắc muốn kích hoạt lại ${label} này?`
        : `Bạn có chắc muốn ngừng bán ${label} này?`;
  return (
    <div
      className="dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && close()}
    >
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title}>
        <h2 className="font-serif text-2xl font-bold">{title}</h2>
        <p className="mt-4">{message}</p>
        <dl className="mt-4 rounded-lg bg-stone-50 p-3">
          <dt className="text-sm text-stone-500">Lựa chọn</dt>
          <dd className="font-bold">{action.option.name}</dd>
        </dl>
        {error && (
          <p role="alert" className="mt-4 text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" disabled={busy} onClick={close}>
            Hủy
          </Button>
          <Button
            type="button"
            className={action.kind === "delete" ? "btn-danger" : "btn-primary"}
            disabled={busy}
            onClick={confirm}
          >
            {busy ? "Đang xử lý..." : "Xác nhận"}
          </Button>
        </div>
      </div>
    </div>
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
          ...(editor.size
            ? {}
            : { is_active: form.get("is_active") === "on" }),
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
              ...(editor.topping
                ? {}
                : { is_active: form.get("is_active") === "on" }),
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
              {((editor.kind === "size" && !editor.size) ||
                (editor.kind === "topping" && !editor.topping)) && (
                <label className="flex gap-2">
                  <input
                    name="is_active"
                    type="checkbox"
                    defaultChecked
                  />{" "}
                  Đang bán
                </label>
              )}
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

function optionActionError(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.code === "last_active_variant")
      return "Sản phẩm phải còn ít nhất một size đang bán. Hãy kích hoạt hoặc thêm size khác trước.";
    if (reason.code === "product_inactive")
      return "Hãy kích hoạt sản phẩm trước khi kích hoạt lại size hoặc topping.";
    if (reason.code === "variant_delete_conflict" || reason.code === "topping_delete_conflict")
      return "Lựa chọn vừa phát sinh dữ liệu liên quan nên chưa thể xóa. Vui lòng tải lại và thử ngừng bán.";
    if (reason.code === "variant_not_found" || reason.code === "topping_not_found")
      return "Lựa chọn không còn tồn tại. Danh sách sẽ được tải lại ở lần thao tác tiếp theo.";
  }
  return reason instanceof Error ? reason.message : "Không thể cập nhật lựa chọn";
}
