import { afterEach, expect, it, vi } from "vitest";
import { configureApi, request } from "../lib/api";

afterEach(() => vi.unstubAllGlobals());

it("explains that the backend is unavailable when the dev proxy fails", async () => {
  configureApi({
    getAccessToken: () => null,
    refresh: async () => null,
    unauthorized: () => undefined,
  });
  vi.stubGlobal("fetch", vi.fn(async () => new Response("Proxy error", { status: 500 })));

  await expect(request("/auth/login", { method: "POST", body: "{}" })).rejects.toEqual(
    expect.objectContaining({
      status: 500,
      code: "backend_unavailable",
    }),
  );
});
