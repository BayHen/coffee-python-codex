import { describe, expect, it } from "vitest";
import { normalizeRevenueSummary, type RevenueSummaryResponse } from "../lib/reporting";

const base: RevenueSummaryResponse = {
  date_from: "2026-10-01",
  date_to: "2026-10-20",
  timezone: "Asia/Ho_Chi_Minh",
  total_revenue: "0.00",
  valid_order_count: 0,
  average_order_value: "0.00",
  refunded_amount: "0.00",
  refunded_payment_count: 0,
  paid_session_count: 0,
};

describe("normalizeRevenueSummary", () => {
  it("preserves valid zero revenue values", () => {
    const result = normalizeRevenueSummary({
      ...base,
      cash_revenue: "0.00",
      bank_transfer_revenue: "0.00",
    });

    expect(result.cash_revenue).toBe("0.00");
    expect(result.bank_transfer_revenue).toBe("0.00");
    expect(result.paid_session_count).toBe(0);
  });

  it("supports the documented revenue_by_method representation", () => {
    const result = normalizeRevenueSummary({
      ...base,
      revenue_by_method: { cash: "125000.00", bank_transfer: "50000.00" },
    });

    expect(result.cash_revenue).toBe("125000.00");
    expect(result.bank_transfer_revenue).toBe("50000.00");
  });

  it("rejects a stale response that omits payment-method revenue", () => {
    expect(() => normalizeRevenueSummary(base)).toThrow(
      "API báo cáo thiếu doanh thu theo phương thức thanh toán",
    );
  });
});
