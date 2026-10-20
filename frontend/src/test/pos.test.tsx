import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { configureApi } from "../lib/api";
import { PosPage } from "../pages/PosPage";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("creates a POS order using variant and quantity without sending client prices", async () => {
  configureApi({ getAccessToken: () => "access", refresh: async () => null, unauthorized: () => undefined });
  const productPage = { items: [{ id: 4, category_id: 1, name: "Cà phê sữa", is_active: true, category: { id: 1, name: "Coffee" }, variants: [{ id: 9, product_id: 4, sku: "CF-S-M", name: "M", price: "35000.00", is_active: true }] }], total: 1, page: 1, page_size: 100, pages: 1 };
  const created = { id: 31, customer_id: null, employee_id: 2, status: "draft", subtotal_amount: "70000.00", discount_percent: "0.00", discount_amount: "0.00", total_amount: "70000.00", created_at: new Date().toISOString(), items: [], events: [], payments: [] };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => String(input).includes("/products") ? json(productPage) : json(created, init?.method === "POST" ? 201 : 200));
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  render(<PosPage />);
  await user.click(await screen.findByRole("button", { name: /Cà phê sữa/ }));
  await user.click(screen.getByRole("button", { name: "Tăng số lượng" }));
  await user.click(screen.getByRole("button", { name: "Tạo đơn nháp" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Đã tạo đơn #31");
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  const [, init] = fetchMock.mock.calls[1] as [RequestInfo | URL, RequestInit];
  const payload = JSON.parse(String(init.body));
  expect(payload.items).toEqual([{ variant_id: 9, quantity: 2 }]);
  expect(payload).not.toHaveProperty("total_amount");
  expect(payload).not.toHaveProperty("unit_price");
  expect(new Headers(init.headers).get("Idempotency-Key")).toMatch(/^pos-order:/);
});
