import type { RevenueSummary } from "../types";

export type RevenueSummaryResponse = Omit<
  RevenueSummary,
  "cash_revenue" | "bank_transfer_revenue" | "paid_session_count" | "revenue_by_method"
> & Partial<
  Pick<
    RevenueSummary,
    "cash_revenue" | "bank_transfer_revenue" | "paid_session_count" | "revenue_by_method"
  >
>;

export function normalizeRevenueSummary(response: RevenueSummaryResponse): RevenueSummary {
  const cashRevenue = response.cash_revenue ?? response.revenue_by_method?.cash;
  const bankTransferRevenue = response.bank_transfer_revenue
    ?? response.revenue_by_method?.bank_transfer;

  if (cashRevenue == null || bankTransferRevenue == null) {
    throw new Error("API báo cáo thiếu doanh thu theo phương thức thanh toán");
  }
  if (response.paid_session_count == null) {
    throw new Error("API báo cáo thiếu số phiên đã thanh toán");
  }

  return {
    ...response,
    cash_revenue: cashRevenue,
    bank_transfer_revenue: bankTransferRevenue,
    paid_session_count: response.paid_session_count,
    revenue_by_method: response.revenue_by_method ?? {
      cash: cashRevenue,
      bank_transfer: bankTransferRevenue,
    },
  };
}
