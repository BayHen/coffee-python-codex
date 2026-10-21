import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

describe("generated immutable variant SKU", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.replaceState({}, "", "/");
  });

  it("does not request SKU and never sends it when creating or editing a size", async () => {
    window.history.replaceState({}, "", "/login");
    const requests: Array<{ url: string; method: string; body: Record<string, unknown> }> = [];
    const product = {
      id: 10,
      category_id: 3,
      name: "Cà phê muối",
      base_price: "32000.00",
      is_active: true,
      category: { id: 3, name: "Cà phê" },
      variants: [{ id: 20, product_id: 10, sku: "VAR-000020", name: "M", price: "5000.00", is_active: true }],
      toppings: [],
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/login")) return json({ access_token: "access", refresh_token: "refresh", token_type: "bearer", expires_in: 900 });
      if (url.endsWith("/auth/me")) return json({ id: 1, email: "manager@example.com", role: "Manager", is_active: true });
      if (url.includes("/reports/revenue/summary")) return json({ date_from: "2026-10-01", date_to: "2026-10-21", timezone: "Asia/Ho_Chi_Minh", total_revenue: "0.00", valid_order_count: 0, average_order_value: "0.00", refunded_amount: "0.00", refunded_payment_count: 0, cash_revenue: "0.00", bank_transfer_revenue: "0.00", paid_session_count: 0, revenue_by_method: {} });
      if (url.includes("/reports/revenue/daily")) return json({ date_from: "2026-10-01", date_to: "2026-10-21", timezone: "Asia/Ho_Chi_Minh", items: [] });
      if (url.includes("/reports/top-products")) return json({ date_from: "2026-10-01", date_to: "2026-10-21", timezone: "Asia/Ho_Chi_Minh", items: [] });
      if (url.includes("/categories?page_size=100")) return json({ items: [product.category], total: 1, page: 1, page_size: 100, pages: 1 });
      if (url.includes("/products?") && !init?.method) return json({ items: [product], total: 1, page: 1, page_size: 100, pages: 1 });
      if (url.endsWith("/products/10/variants") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        requests.push({ url, method: init.method, body });
        return json({ id: 21, product_id: 10, sku: "VAR-000021", ...body }, 201);
      }
      if (url.endsWith("/products/10/variants/20") && init?.method === "PATCH") {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        requests.push({ url, method: init.method, body });
        return json({ ...product.variants[0], ...body });
      }
      return json({ detail: "Not found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("Email"), "manager@example.com");
    await user.type(screen.getByLabelText("Mật khẩu"), "password");
    await user.click(screen.getByRole("button", { name: "Vào bảng điều hành" }));
    await user.click(await screen.findByRole("link", { name: "Products" }));

    await user.click(await screen.findByRole("button", { name: "Sửa size M" }));
    const editDialog = screen.getByRole("dialog", { name: "Chỉnh sửa size" });
    expect(within(editDialog).getByTestId("variant-sku")).toHaveTextContent("VAR-000020");
    expect(within(editDialog).queryByRole("textbox", { name: /SKU/i })).not.toBeInTheDocument();
    await user.clear(within(editDialog).getByLabelText("Giá upsize (VND)"));
    await user.type(within(editDialog).getByLabelText("Giá upsize (VND)"), "7000");
    await user.click(within(editDialog).getByRole("button", { name: "Lưu" }));

    await user.click((await screen.findAllByRole("button", { name: "+ Thêm" }))[0]);
    const createDialog = screen.getByRole("dialog", { name: "Thêm size" });
    expect(within(createDialog).queryByText(/SKU/i)).not.toBeInTheDocument();
    await user.type(within(createDialog).getByLabelText("Tên size"), "L");
    await user.type(within(createDialog).getByLabelText("Giá upsize (VND)"), "10000");
    await user.click(within(createDialog).getByRole("button", { name: "Lưu" }));

    expect(requests).toHaveLength(2);
    expect(requests[0].body).toEqual({ name: "M", price: "7000", is_active: true });
    expect(requests[1].body).toEqual({ name: "L", price: "10000", is_active: true });
    expect(requests.every((entry) => !("sku" in entry.body))).toBe(true);
  });
});
