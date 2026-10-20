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
    expect(screen.getByText("manager@example.com")).toBeInTheDocument();
    expect(localStorage).toHaveLength(0);
    expect(sessionStorage).toHaveLength(0);
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
});
