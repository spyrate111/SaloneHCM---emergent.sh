import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import api, { getToken, setToken, clearToken } from "../lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const tok = getToken();
    if (!tok) {
      setLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then((r) => setUser(r.data))
      .catch((err) => {
        console.warn("[Auth] session restore failed:", err?.message || err);
        clearToken();
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setToken(data.token);
    setUser({
      id: data.id,
      email: data.email,
      name: data.name,
      role: data.role,
      employee_id: data.employee_id,
      company_id: data.company_id,
      company: data.company,
    });
    return data;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) {
      console.warn("[Auth] logout request failed (proceeding to clear local session):", err?.message || err);
    }
    clearToken();
    setUser(null);
  }, []);

  const refetch = useCallback(async () => {
    try {
      const r = await api.get("/auth/me");
      setUser(r.data);
      return r.data;
    } catch (err) {
      console.warn("[Auth] refetch failed:", err?.message || err);
      return null;
    }
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout, refetch }), [user, loading, login, logout, refetch]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
