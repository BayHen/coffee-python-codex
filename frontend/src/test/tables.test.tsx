import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { OrdersPage } from "../pages/OrdersPage";

const json = (body: unknown) => new Response(JSON.stringify(body), {
  status: 200,
  headers: { "Content-Type": "application/json" },
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("loads persisted table session history and separates draft from payable total", async () => {
  const tables = [{
    id: 5, table_number: "05", name: "Window", is_active: true,
    status: "occupied", current_bill_total: "58000.00", active_session_id: 9,
  }];
  const session = {
    id: 9, table_id: 5, status: "open", opened_at: new Date().toISOString(),
    closed_at: null, opened_by: 2,
    bill: { confirmed_subtotal: "58000.00", draft_subtotal: "32000.00", payable_total: "58000.00" },
    orders: [
      { id: 1, session_id: 9, order_type: "initial", sequence_number: 1, status: "confirmed", subtotal_amount: "58000.00", total_amount: "58000.00", confirmed_by: 2, confirmed_at: new Date().toISOString(), created_at: new Date().toISOString(), items: [] },
      { id: 2, session_id: 9, order_type: "additional", sequence_number: 2, status: "draft", subtotal_amount: "32000.00", total_amount: "32000.00", confirmed_by: null, confirmed_at: null, created_at: new Date().toISOString(), items: [] },
    ],
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) =>
    String(input).includes("active-session") ? json(session) : json(tables)));
  const user = userEvent.setup();
  render(<AuthProvider><OrdersPage /></AuthProvider>);

  await user.click(await screen.findByRole("button", { name: /Bàn 05/i }));

  expect(await screen.findByText(/Initial Order/)).toBeInTheDocument();
  expect(screen.getAllByText(/Additional Order/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/58\.000/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/32\.000/).length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: /Add Additional Order/i })).toBeDisabled();
});

it("selects a product safely and shows the final size price", async () => {
  const tables = [{
    id: 5, table_number: "05", name: "Window", is_active: true,
    status: "occupied", current_bill_total: "0.00", active_session_id: 9,
  }];
  const products = { items: [{
    id: 1, category_id: 1, name: "Cà phê muối", base_price: "25000.00",
    is_active: true, category: { id: 1, name: "Coffee" }, toppings: [],
    variants: [{ id: 2, product_id: 1, sku: "CFM-M", name: "M", price: "5000.00", is_active: true }],
  }], total: 1, page: 1, page_size: 100, pages: 1 };
  const session = {
    id: 9, table_id: 5, status: "open", opened_at: new Date().toISOString(),
    closed_at: null, opened_by: 2,
    bill: { confirmed_subtotal: "0.00", draft_subtotal: "0.00", payable_total: "0.00" },
    orders: [{ id: 2, session_id: 9, order_type: "initial", sequence_number: 1, status: "draft", subtotal_amount: "0.00", total_amount: "0.00", confirmed_by: null, confirmed_at: null, created_at: new Date().toISOString(), items: [] }],
  };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/products")) return json(products);
    if (url.includes("active-session")) return json(session);
    return json(tables);
  }));
  const user = userEvent.setup();
  render(<AuthProvider><OrdersPage /></AuthProvider>);

  await user.click(await screen.findByRole("button", { name: /Bàn 05/i }));
  await user.selectOptions(await screen.findByLabelText("Chọn sản phẩm"), "1");

  expect(screen.getByRole("option", { name: /M · 30\.000/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Thêm · 30\.000/ })).toBeEnabled();
});
