export type Role = "Admin" | "Manager" | "Staff";
export type User = {
  id: number;
  email: string;
  role: Role;
  is_active: boolean;
};
export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
};
export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};
export type Category = { id: number; name: string };
export type Variant = {
  id: number;
  product_id: number;
  sku: string;
  name: string;
  price: string;
  is_active: boolean;
};
export type Topping = {
  id: number;
  product_id: number;
  name: string;
  price: string;
  is_active: boolean;
};
export type Product = {
  id: number;
  category_id: number;
  name: string;
  base_price: string;
  is_active: boolean;
  category: Category;
  variants: Variant[];
  toppings: Topping[];
};
export type OrderStatus = "draft" | "placed" | "paid" | "cancelled";
export type ItemTopping = { id: number; name: string; price: string };
export type OrderItem = {
  id: number;
  variant_id: number;
  product_name: string;
  variant_name: string;
  sku: string;
  quantity: number;
  unit_price: string;
  line_total: string;
  topping_snapshots: ItemTopping[];
};
export type Payment = {
  id: number;
  order_id: number;
  method: string;
  status: string;
  amount: string;
  provider_reference: string | null;
  created_at: string;
};
export type Order = {
  id: number;
  customer_id: number | null;
  employee_id: number | null;
  status: OrderStatus;
  subtotal_amount: string;
  discount_percent: string;
  discount_amount: string;
  total_amount: string;
  created_at: string;
  items: OrderItem[];
  events: unknown[];
  payments: Payment[];
};
export type CafeTable = {
  id: number;
  table_number: string;
  name: string;
  is_active: boolean;
  status: "available" | "occupied";
  current_bill_total: string;
  active_session_id: number | null;
};
export type SessionOrder = {
  id: number;
  session_id: number;
  order_type: "initial" | "additional";
  sequence_number: number;
  status: "draft" | "confirmed" | "cancelled";
  subtotal_amount: string;
  total_amount: string;
  confirmed_by: number | null;
  confirmed_at: string | null;
  created_at: string;
  items: OrderItem[];
};
export type Bill = {
  confirmed_subtotal: string;
  draft_subtotal: string;
  payable_total: string;
};
export type TableSession = {
  id: number;
  table_id: number;
  status: "open" | "paid" | "cancelled";
  opened_at: string;
  closed_at: string | null;
  opened_by: number;
  orders: SessionOrder[];
  bill: Bill;
};
export type SessionPayment = {
  id: number;
  session_id: number;
  method: string;
  status: string;
  amount: string;
  provider_reference: string | null;
  receipt_number: string;
  cashier_id: number;
  paid_at: string;
  cash_received: string | null;
  change_amount: string | null;
  transfer_reference: string | null;
  created_at: string;
};
export type BankTransfer = {
  available: boolean;
  bank_name: string | null;
  bank_id: string | null;
  account_number: string | null;
  account_holder: string | null;
  payment_reference: string;
  qr_image_url: string | null;
};
export type Ingredient = {
  id: number;
  sku: string;
  name: string;
  unit: "g" | "ml" | "piece";
  low_stock_threshold: string;
  current_stock: string;
  is_low_stock: boolean;
  is_active: boolean;
};
export type InventoryTransaction = {
  id: number;
  ingredient_id: number;
  order_item_id: number | null;
  actor_user_id: number | null;
  reversal_of_id: number | null;
  transaction_type: string;
  quantity_delta: string;
  reason: string;
  created_at: string;
};
export type RevenueSummary = {
  date_from: string;
  date_to: string;
  timezone: string;
  total_revenue: string;
  valid_order_count: number;
  average_order_value: string;
  refunded_amount: string;
  refunded_payment_count: number;
  cash_revenue: string;
  bank_transfer_revenue: string;
  paid_session_count: number;
  revenue_by_method: Record<string, string>;
};
export type DailyRevenuePoint = {
  date: string;
  revenue: string;
  order_count: number;
};
export type DailyRevenueReport = {
  date_from: string;
  date_to: string;
  timezone: string;
  items: DailyRevenuePoint[];
};
export type TopProduct = {
  product_name: string;
  variant_name: string;
  sku: string;
  quantity_sold: number;
  gross_item_sales: string;
};
export type TopProductsReport = {
  date_from: string;
  date_to: string;
  timezone: string;
  items: TopProduct[];
};
export type AIChatResponse = {
  answer: string;
  highlights: string[];
  recommendations: string[];
  tools_used: string[];
  request_id: string;
};

export function money(value: string | number | null | undefined): string {
  const amount = value == null || (typeof value === "string" && value.trim() === "")
    ? Number.NaN
    : Number(value);
  if (!Number.isFinite(amount)) return "—";
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(amount);
}
