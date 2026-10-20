import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("authentication workflow", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState({}, "", "/"); });

  it("logs in, loads the dashboard, and does not persist tokens", async () => {
    window.history.replaceState({}, "", "/login");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/login")) return json({ access_token: "access", refresh_token: "refresh", token_type: "bearer", expires_in: 900 });
      if (url.endsWith("/auth/me")) return json({ id: 1, email: "manager@example.com", role: "Manager", is_active: true });
      if (url.includes("/reports/revenue/summary")) return json({ date_from: "2026-10-01", date_to: "2026-10-20", timezone: "Asia/Ho_Chi_Minh", total_revenue: "145.00", valid_order_count: 2, average_order_value: "72.50", refunded_amount: "0.00", refunded_payment_count: 0, cash_revenue: "145.00", bank_transfer_revenue: "0.00", paid_session_count: 0, revenue_by_method: { cash: "145.00", bank_transfer: "0.00" } });
      if (url.includes("/reports/revenue/daily")) return json({ date_from: "2026-10-01", date_to: "2026-10-20", timezone: "Asia/Ho_Chi_Minh", items: [{ date: "2026-10-20", revenue: "145.00", order_count: 2 }] });
      if (url.includes("/reports/top-products")) return json({ date_from: "2026-10-01", date_to: "2026-10-20", timezone: "Asia/Ho_Chi_Minh", items: [{ product_name: "Latte", variant_name: "M", sku: "LATTE-M", quantity_sold: 3, gross_item_sales: "145.00" }] });
      if (url.endsWith("/ai/chat")) return json({ answer: "Doanh thu là 145.00 VND.", highlights: ["2 đơn hợp lệ"], recommendations: ["Theo dõi nguyên liệu tồn thấp"], tools_used: ["get_revenue_summary"], request_id: "request-1" });
      if (url.includes("/products")) return json({ items: [], total: 0, page: 1, page_size: 1, pages: 0 });
      if (url.includes("/orders")) return json({ items: [], total: 0, page: 1, page_size: 5, pages: 0 });
      if (url.includes("/ingredients/low-stock")) return json({ items: [], total: 0, page: 1, page_size: 100, pages: 0 });
      return json({ detail: "Not found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Email"), "manager@example.com");
    await user.type(screen.getByLabelText("Mật khẩu"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Vào bảng điều hành" }));
    expect(await screen.findByRole("heading", { name: "Tổng quan" })).toBeInTheDocument();
    expect(await screen.findByText("Doanh thu theo ngày")).toBeInTheDocument();
    expect(screen.getByText("Latte · M")).toBeInTheDocument();
    expect(screen.getByText("manager@example.com")).toBeInTheDocument();
    expect(localStorage).toHaveLength(0);
    expect(sessionStorage).toHaveLength(0);
    await user.click(screen.getByRole("link", { name: "Trợ lý AI" }));
    expect(await screen.findByRole("heading", { name: "Trợ lý quản lý" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Câu hỏi"), "Doanh thu tháng này?");
    await user.click(screen.getByRole("button", { name: "Gửi" }));
    expect(await screen.findByText("Doanh thu là 145.00 VND.")).toBeInTheDocument();
  });

  it("shows the backend error for invalid credentials", async () => {
    window.history.replaceState({}, "", "/login");
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "Invalid email or password" }, 401)));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Email"), "staff@example.com");
    await user.type(screen.getByLabelText("Mật khẩu"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Vào bảng điều hành" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
  });

  it("does not request financial reports for staff", async () => {
    window.history.replaceState({}, "", "/login");
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/login")) return json({ access_token: "access", refresh_token: "refresh", token_type: "bearer", expires_in: 900 });
      if (url.endsWith("/auth/me")) return json({ id: 2, email: "staff@example.com", role: "Staff", is_active: true });
      if (url.includes("/products")) return json({ items: [], total: 4, page: 1, page_size: 1, pages: 4 });
      if (url.includes("/orders")) return json({ items: [], total: 3, page: 1, page_size: 5, pages: 1 });
      if (url.includes("/ingredients/low-stock")) return json({ items: [], total: 1, page: 1, page_size: 100, pages: 1 });
      return json({ detail: "Not found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText("Email"), "staff@example.com");
    await user.type(screen.getByLabelText("Mật khẩu"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Vào bảng điều hành" }));
    expect(await screen.findByText("Tổng số đơn")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/reports/"))).toBe(false);
  });
});
