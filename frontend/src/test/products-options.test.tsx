import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("product option lifecycle", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.replaceState({}, "", "/");
  });

  it("filters, confirms status changes, and reflects delete fallback", async () => {
    window.history.replaceState({}, "", "/login");
    const product = {
      id: 10,
      category_id: 3,
      name: "Cà phê muối",
      base_price: "32000.00",
      is_active: true,
      category: { id: 3, name: "Cà phê" },
      variants: [
        { id: 20, product_id: 10, sku: "VAR-000020", name: "M", price: "5000.00", is_active: true },
        { id: 21, product_id: 10, sku: "VAR-000021", name: "L", price: "10000.00", is_active: false },
      ],
      toppings: [
        { id: 30, product_id: 10, name: "Foam", price: "3000.00", is_active: true },
        { id: 31, product_id: 10, name: "Pearl", price: "5000.00", is_active: false },
      ],
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/login")) return json({ access_token: "access", refresh_token: "refresh", token_type: "bearer", expires_in: 900 });
      if (url.endsWith("/auth/me")) return json({ id: 1, email: "manager@example.com", role: "Manager", is_active: true });
      if (url.includes("/reports/revenue/summary")) return json({ date_from: "2026-10-01", date_to: "2026-10-21", timezone: "Asia/Ho_Chi_Minh", total_revenue: "0.00", valid_order_count: 0, average_order_value: "0.00", refunded_amount: "0.00", refunded_payment_count: 0, cash_revenue: "0.00", bank_transfer_revenue: "0.00", paid_session_count: 0, revenue_by_method: {} });
      if (url.includes("/reports/revenue/daily")) return json({ date_from: "2026-10-01", date_to: "2026-10-21", timezone: "Asia/Ho_Chi_Minh", items: [] });
      if (url.includes("/reports/top-products")) return json({ date_from: "2026-10-01", date_to: "2026-10-21", timezone: "Asia/Ho_Chi_Minh", items: [] });
      if (url.includes("/categories?page_size=100")) return json({ items: [product.category], total: 1, page: 1, page_size: 100, pages: 1 });
      if (url.includes("/products?") && !init?.method) return json({ items: [structuredClone(product)], total: 1, page: 1, page_size: 100, pages: 1 });
      if (url.endsWith("/products/10/variants/20/status") && init?.method === "PATCH") {
        expect(JSON.parse(String(init.body))).toEqual({ is_active: false });
        product.variants[0].is_active = false;
        return json(product.variants[0]);
      }
      if (url.endsWith("/products/10/toppings/30") && init?.method === "DELETE") {
        product.toppings[0].is_active = false;
        return json({ entity_type: "topping", entity_id: 30, action: "deactivated", is_active: false });
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

    const filters = await screen.findByRole("group", { name: "Lọc trạng thái size và topping" });
    await user.click(within(filters).getByRole("button", { name: "Đang bán" }));
    expect(screen.getByText("M")).toBeInTheDocument();
    expect(screen.queryByText("L")).not.toBeInTheDocument();
    expect(screen.getByText("Foam")).toBeInTheDocument();
    expect(screen.queryByText("Pearl")).not.toBeInTheDocument();

    await user.click(within(filters).getByRole("button", { name: "Ngừng bán" }));
    expect(screen.getByText("L")).toBeInTheDocument();
    expect(screen.getByText("Pearl")).toBeInTheDocument();
    expect(screen.queryByText("M")).not.toBeInTheDocument();

    await user.click(within(filters).getByRole("button", { name: "Tất cả" }));
    await user.click(screen.getByRole("button", { name: "Ngừng bán size M" }));
    const statusDialog = screen.getByRole("dialog", { name: "Ngừng bán Size" });
    await user.click(within(statusDialog).getByRole("button", { name: "Xác nhận" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Đã ngừng bán lựa chọn");

    await user.click(screen.getByRole("button", { name: "Xóa topping Foam" }));
    const deleteDialog = screen.getByRole("dialog", { name: "Xóa Topping" });
    expect(deleteDialog).toHaveTextContent("Nếu đã được sử dụng");
    await user.click(within(deleteDialog).getByRole("button", { name: "Xác nhận" }));
    expect(await screen.findByRole("status")).toHaveTextContent("ngừng bán thay vì xóa lịch sử");

    await user.click(within(filters).getByRole("button", { name: "Đang bán" }));
    expect(screen.getByText("Không có size phù hợp bộ lọc.")).toBeInTheDocument();
    expect(screen.getByText("Không có topping phù hợp bộ lọc.")).toBeInTheDocument();
  });
});
