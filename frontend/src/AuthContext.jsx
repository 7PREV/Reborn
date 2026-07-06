import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import api, { authRefresh, authRevoke, authSessions, collectSecurityTokens } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (email, password) => {
    const { csrfToken, recaptchaToken, turnstileToken } = collectSecurityTokens();
    const { data } = await api.post("/auth/login", {
      email,
      password,
      csrf_token: csrfToken || undefined,
      recaptcha_token: recaptchaToken || undefined,
      cf_turnstile_response: turnstileToken || undefined,
    });
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authRevoke();
      await api.post("/auth/logout");
    } catch {
      // ignore — clearing local state is the goal
    }
    setUser(false);
  }, []);

  const refreshToken = useCallback(async () => {
    await authRefresh();
    await refresh();
  }, [refresh]);

  const listSessions = useCallback(async () => {
    const { data } = await authSessions();
    return data;
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refresh, refreshToken, listSessions }),
    [user, loading, login, register, logout, refresh, refreshToken, listSessions]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
