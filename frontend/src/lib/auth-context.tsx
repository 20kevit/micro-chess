// Account authentication state. Screens consume useAuth() for the
// current user, loading/error states, and session actions. The backend
// remains authoritative: roles and capabilities only render here.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, apiStatus, clearToken, getToken, setToken } from "../api/client";
import type { AuthUser } from "../api/types";

export interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  error: string;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function describeError(e: unknown): string {
  const status = apiStatus(e);
  if (status === 401) return "unauthorized";
  if (status === 429) return "rate_limited";
  return "request_failed";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setUser(await api.me());
      setError("");
    } catch (e) {
      // Invalid/expired/revoked token: drop it so the app falls back to
      // anonymous local progress instead of failing every request.
      if (apiStatus(e) === 401) {
        clearToken();
        setUser(null);
        setError("");
      } else {
        setError(describeError(e));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(async (username: string, password: string) => {
    setLoading(true);
    try {
      const token = await api.login({ username, password });
      setToken(token.access_token);
      setUser(await api.me());
      setError("");
    } catch (e) {
      setError(describeError(e));
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    setLoading(true);
    try {
      const token = await api.register({ username, password });
      setToken(token.access_token);
      setUser(await api.me());
      setError("");
    } catch (e) {
      setError(describeError(e));
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Best effort: the session ends locally even if the request fails.
    } finally {
      clearToken();
      setUser(null);
      setError("");
      setLoading(false);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, loading, error, login, register, logout, refresh }),
    [user, loading, error, login, register, logout, refresh],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth must be used within AuthProvider");
  return state;
}
