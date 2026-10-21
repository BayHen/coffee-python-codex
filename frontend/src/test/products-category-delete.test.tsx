import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

describe("category reassignment before deletion", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.replaceState({}, "", "/");
  });

  it("preselects Trà and refreshes products after confirmation", async () => {
    window.history.replaceState({}, "", "/login");
    let deleted = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/login")) return json({ access_token: "access", refresh_token: "refresh", token_type: "bearer", expires_in: 900 });
      if (url.endsWith("/auth/me")) return json({ id: 1, email: "manager@example.com", role: "Manager", is_active: true });
      if (url.includes("/reports/revenue/summary")) return json({ date_from: "2026-10-01", date_to: "2026-10-21", timezone: "Asia/Ho_Chi_Minh", total_revenue: "0.00", valid_order_count: 0, average_order_value: "0.00", refunded_amount: "0.00", refunded_payment_count: 0, cash_revenue: "0.00", bank_transfer_revenue: "0.00", paid_session_count: 0, revenue_by_method: { cash: "0.00", bank_transfer: "0.00" } });
      if (url.includes("/reports/revenue/daily")) return json({ date_from: "2026-10-01", date_to: "2026-10-21", timezone: "Asia/Ho_Chi_Minh", items: [] });
      if (url.includes("/reports/top-products")) return json({ date_from: "2026-10-01", date_to: "2026-10-21", timezone: "Asia/Ho_Chi_Minh", items: [] });
      if (url.endsWith("/categories/3/deletion-options")) return json({ category: { id: 3, name: "Cafe" }, linked_product_count: 2, replacement_categories: [{ id: 4, name: "Trà" }, { id: 5, name: "Nước ép" }], preferred_replacement_category_id: 4 });
      if (url.endsWith("/categories/3/reassign-and-delete") && init?.method === "POST") {
        expect(JSON.parse(String(init.body))).toEqual({ replacement_category_id: 4 });
        deleted = true;
        return json({ deleted_category_id: 3, replacement_category_id: 4, reassigned_product_count: 2 });
      }
      if (url.includes("/categories?page_size=100")) return json({ items: deleted ? [{ id: 4, name: "Trà" }, { id: 5, name: "Nước ép" }] : [{ id: 3, name: "Cafe" }, { id: 4, name: "Trà" }, { id: 5, name: "Nước ép" }], total: deleted ? 2 : 3, page: 1, page_size: 100, pages: 1 });
      if (url.includes("/products?")) return json({ items: deleted ? [] : [{ id: 10, category_id: 3, name: "Cafe muối", base_price: "32000.00", is_active: true, category: { id: 3, name: "Cafe" }, variants: [], toppings: [] }], total: deleted ? 0 : 1, page: 1, page_size: 100, pages: deleted ? 0 : 1 });
      if (url.includes("/orders")) return json({ items: [], total: 0, page: 1, page_size: 5, pages: 0 });
      if (url.includes("/ingredients/low-stock")) return json({ items: [], total: 0, page: 1, page_size: 100, pages: 0 });
      return json({ detail: "Not found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("Email"), "manager@example.com");
    await user.type(screen.getByLabelText("Mật khẩu"), "password");
    await user.click(screen.getByRole("button", { name: "Vào bảng điều hành" }));
    await user.click(await screen.findByRole("link", { name: "Products" }));
    await user.click(await screen.findByRole("button", { name: "Danh mục" }));

    const dialog = screen.getByRole("dialog", { name: "Chỉnh sửa Products" });
    await user.selectOptions(within(dialog).getAllByRole("combobox")[0], "3");
    await user.click(within(dialog).getByRole("button", { name: "Xóa danh mục" }));

    const replacement = await screen.findByRole("combobox", { name: "Danh mục thay thế" });
    expect(replacement).toHaveValue("4");
    expect(screen.getByText("2")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Chuyển sản phẩm và xóa danh mục" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Đã chuyển 2 sản phẩm sang Trà");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
