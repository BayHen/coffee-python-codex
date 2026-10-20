import { describe, expect, it } from "vitest";
import { money } from "../types";

describe("money", () => {
  it("formats valid VND amounts without decimal places", () => {
    expect(money("25000.00")).toContain("25.000");
  });

  it("does not expose NaN for missing or invalid values", () => {
    expect(money(undefined)).toBe("—");
    expect(money(null)).toBe("—");
    expect(money("")).toBe("—");
    expect(money("invalid")).toBe("—");
  });
});
