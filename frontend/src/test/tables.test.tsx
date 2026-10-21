import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AuthProvider } from "../auth/AuthContext";
import { ProductPicker } from "../components/ProductPicker";
import { OrdersPage } from "../pages/OrdersPage";
import type { SessionOrder } from "../types";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

it("hides size and topping sections for a default product and cancel adds nothing", async () => {
  const order: SessionOrder = {
    id: 12, session_id: 3, order_type: "initial", sequence_number: 1,
    status: "draft", subtotal_amount: "0.00", total_amount: "0.00",
    confirmed_by: null, confirmed_at: null, created_at: new Date().toISOString(), items: [],
  };
  const product = {
    id: 8, category_id: 2, name: "Cold brew", base_price: "42000.00",
    is_active: true, category: { id: 2, name: "Coffee" }, toppings: [],
    variants: [{ id: 9, product_id: 8, sku: "AUTO-8", name: "Standard", price: "0.00", is_active: true }],
  };
  const fetchMock = vi.fn(async (...requestArgs: [RequestInfo | URL, RequestInit?]) => {
    void requestArgs;
    return json({ items: [product], total: 1, page: 1, page_size: 20, pages: 1 });
  });
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  render(<ProductPicker order={order} disabled={false} added={vi.fn()} />);

  const search = screen.getByRole("combobox", { name: "Tìm sản phẩm theo tên" });
  await user.type(search, "cold");
  await user.click(await screen.findByRole("option", { name: /Cold brew/ }));
  const dialog = screen.getByRole("dialog", { name: "Cấu hình Cold brew" });
  expect(within(dialog).queryByText("Size")).not.toBeInTheDocument();
  expect(within(dialog).queryByText("Topping")).not.toBeInTheDocument();
  expect(within(dialog).getByLabelText("Số lượng")).toHaveValue(1);
  expect(within(dialog).getByRole("button", { name: /Thêm vào đơn · 42\.000/ })).toBeEnabled();

  await user.click(within(dialog).getByRole("button", { name: "Hủy" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await waitFor(() => expect(search).toHaveFocus());
  expect(fetchMock.mock.calls.every(([, init]) => init?.method !== "POST")).toBe(true);
});

it("keeps the configuration popup and choices when add-to-order fails", async () => {
  const order: SessionOrder = {
    id: 12, session_id: 3, order_type: "additional", sequence_number: 2,
    status: "draft", subtotal_amount: "0.00", total_amount: "0.00",
    confirmed_by: null, confirmed_at: null, created_at: new Date().toISOString(), items: [],
  };
  const product = {
    id: 4, category_id: 2, name: "Latte", base_price: "30000.00",
    is_active: true, category: { id: 2, name: "Coffee" }, toppings: [],
    variants: [{ id: 6, product_id: 4, sku: "LATTE-M", name: "M", price: "5000.00", is_active: true }],
  };
  vi.stubGlobal("fetch", vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) =>
    init?.method === "POST"
      ? json({ detail: { code: "order_not_editable", message: "Only draft orders can be edited" } }, 409)
      : json({ items: [product], total: 1, page: 1, page_size: 20, pages: 1 })));
  const user = userEvent.setup();
  render(<ProductPicker order={order} disabled={false} added={vi.fn()} />);

  await user.type(screen.getByRole("combobox", { name: "Tìm sản phẩm theo tên" }), "latte");
  await user.click(await screen.findByRole("option", { name: /Latte/ }));
  const dialog = screen.getByRole("dialog", { name: "Cấu hình Latte" });
  const selectedSize = within(dialog).getByRole("radio", { name: /M/ });
  expect(selectedSize).toBeChecked();
  await user.click(within(dialog).getByRole("button", { name: /Thêm vào đơn/ }));

  expect(await within(dialog).findByRole("alert")).toHaveTextContent("Đơn đã được xác nhận");
  expect(screen.getByRole("dialog", { name: "Cấu hình Latte" })).toBeInTheDocument();
  expect(selectedSize).toBeChecked();
  expect(within(dialog).getByLabelText("Số lượng")).toHaveValue(1);
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

it("searches without accents and configures size, topping, and quantity in a popup", async () => {
  const tables = [{
    id: 5, table_number: "05", name: "Window", is_active: true,
    status: "occupied", current_bill_total: "0.00", active_session_id: 9,
  }];
  const product = {
    id: 1, category_id: 1, name: "Cà phê muối", base_price: "25000.00",
    is_active: true, category: { id: 1, name: "Coffee" },
    toppings: [{ id: 7, product_id: 1, name: "Kem mặn", price: "7000.00", is_active: true }],
    variants: [
      { id: 2, product_id: 1, sku: "CFM-M", name: "M", price: "5000.00", is_active: true },
      { id: 3, product_id: 1, sku: "CFM-L", name: "L", price: "10000.00", is_active: true },
    ],
  };
  const products = { items: [product], total: 1, page: 1, page_size: 20, pages: 1 };
  const session = {
    id: 9, table_id: 5, status: "open", opened_at: new Date().toISOString(),
    closed_at: null, opened_by: 2,
    bill: { confirmed_subtotal: "0.00", draft_subtotal: "0.00", payable_total: "0.00" },
    orders: [{ id: 2, session_id: 9, order_type: "initial", sequence_number: 1, status: "draft", subtotal_amount: "0.00", total_amount: "0.00", confirmed_by: null, confirmed_at: null, created_at: new Date().toISOString(), items: [] }],
  };
  let added = false;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/products")) return json(products);
    if (url.includes("/orders/2/items") && init?.method === "POST") {
      expect(JSON.parse(String(init.body))).toEqual({ product_id: 1, variant_id: 2, topping_ids: [7], quantity: 2 });
      expect(new Headers(init.headers).get("Idempotency-Key")).toMatch(/^order-item-2:/);
      added = true;
      return json({ ...session.orders[0], total_amount: "74000.00", items: [{ id: 20, variant_id: 2, product_name: product.name, variant_name: "M", sku: "CFM-M", quantity: 2, unit_price: "37000.00", line_total: "74000.00", topping_snapshots: [{ id: 1, name: "Kem mặn", price: "7000.00" }] }] });
    }
    if (url.includes("active-session")) return json(added ? { ...session, orders: [{ ...session.orders[0], total_amount: "74000.00", items: [{ id: 20, variant_id: 2, product_name: product.name, variant_name: "M", sku: "CFM-M", quantity: 2, unit_price: "37000.00", line_total: "74000.00", topping_snapshots: [{ id: 1, name: "Kem mặn", price: "7000.00" }] }] }] } : session);
    return json(tables);
  });
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();
  render(<AuthProvider><OrdersPage /></AuthProvider>);

  await user.click(await screen.findByRole("button", { name: /Bàn 05/i }));
  const search = await screen.findByRole("combobox", { name: "Tìm sản phẩm theo tên" });
  await user.type(search, "ca phe muoi");
  const option = await screen.findByRole("option", { name: /Cà phê muối/ });
  expect(option).toHaveTextContent("Coffee");
  await user.keyboard("{Enter}");

  const dialog = await screen.findByRole("dialog", { name: "Cấu hình Cà phê muối" });
  expect(within(dialog).getByRole("button", { name: /Thêm vào đơn/ })).toBeDisabled();
  await user.click(within(dialog).getByRole("radio", { name: /M/ }));
  await user.click(within(dialog).getByRole("checkbox", { name: /Kem mặn/ }));
  await user.click(within(dialog).getByRole("button", { name: "Tăng số lượng" }));
  const addButton = within(dialog).getByRole("button", { name: /Thêm vào đơn · 74\.000/ });
  expect(addButton).toBeEnabled();
  await user.click(addButton);

  expect(await screen.findByText(/Cà phê muối · M/)).toBeInTheDocument();
  expect(screen.queryByRole("dialog", { name: "Cấu hình Cà phê muối" })).not.toBeInTheDocument();
  await waitFor(() => expect(search).toHaveFocus());
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("search=ca+phe+muoi"))).toBe(true);
});
