import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { configureApi, request } from "../lib/api";
import type { Role, TokenPair, User } from "../types";

type AuthValue = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  canManage: boolean;
  hasRole: (...roles: Role[]) => boolean;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const tokens = useRef<TokenPair | null>(null);
  const refreshing = useRef<Promise<TokenPair | null> | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);

  const clear = useCallback(() => {
    tokens.current = null;
    setUser(null);
  }, []);

  const refresh = useCallback(() => {
    if (refreshing.current) return refreshing.current;
    refreshing.current = (async () => {
      const refreshToken = tokens.current?.refresh_token;
      if (!refreshToken) return null;
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? "/api"}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        clear();
        return null;
      }
      const pair = (await response.json()) as TokenPair;
      tokens.current = pair;
      return pair;
    })().finally(() => { refreshing.current = null; });
    return refreshing.current;
  }, [clear]);

  useEffect(() => {
    configureApi({ getAccessToken: () => tokens.current?.access_token ?? null, refresh, unauthorized: clear });
  }, [clear, refresh]);

  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    try {
      const pair = await request<TokenPair>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      tokens.current = pair;
      const current = await request<User>("/auth/me");
      setUser(current);
    } catch (error) {
      clear();
      throw error;
    } finally {
      setLoading(false);
    }
  }, [clear]);

  const logout = useCallback(async () => {
    const refreshToken = tokens.current?.refresh_token;
    try {
      if (refreshToken) await request<void>("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) }, false);
    } finally {
      clear();
    }
  }, [clear]);

  const value = useMemo<AuthValue>(() => ({
    user,
    loading,
    login,
    logout,
    canManage: user?.role === "Admin" || user?.role === "Manager",
    hasRole: (...roles) => user !== null && roles.includes(user.role),
  }), [user, loading, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// The hook intentionally shares the provider module to keep this small context cohesive.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
