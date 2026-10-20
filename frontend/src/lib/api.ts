import type { TokenPair } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
  }
}

type SessionHooks = {
  getAccessToken: () => string | null;
  refresh: () => Promise<TokenPair | null>;
  unauthorized: () => void;
};

let session: SessionHooks = {
  getAccessToken: () => null,
  refresh: async () => null,
  unauthorized: () => undefined,
};

export function configureApi(hooks: SessionHooks) {
  session = hooks;
}

async function errorFrom(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null);
  const detail = body?.detail;
  if (typeof detail === "string") return new ApiError(response.status, detail);
  if (detail?.message) return new ApiError(response.status, detail.message, detail.code);
  if (Array.isArray(detail)) {
    const issue = detail[0];
    const field = Array.isArray(issue?.loc) ? issue.loc.slice(1).join(".") : "";
    const message = issue?.msg ?? "Dữ liệu không hợp lệ";
    return new ApiError(response.status, field ? `${field}: ${message}` : message, issue?.type);
  }
  if (response.status >= 500) {
    return new ApiError(
      response.status,
      "Backend API không phản hồi. Hãy chạy API tại cổng 8000 rồi thử lại.",
      "backend_unavailable",
    );
  }
  return new ApiError(response.status, "Không thể hoàn tất yêu cầu");
}

export async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = session.getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers,
  });
  if (response.status === 401 && token && retry) {
    const pair = await session.refresh();
    if (pair) return request<T>(path, init, false);
    session.unauthorized();
  }
  if (!response.ok) throw await errorFrom(response);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function idempotencyKey(prefix: string): string {
  return `${prefix}:${crypto.randomUUID()}`;
}
