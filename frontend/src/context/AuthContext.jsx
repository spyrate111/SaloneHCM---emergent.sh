import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import api from "../lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .get("/auth/me")
      .then((r) => {
        if (!cancelled) setUser(r.data);
      })
      .catch((err) => {
        if (err?.response?.status !== 401 && err?.response?.status !== 403) {
          console.warn("[Auth] session restore failed:", err?.message || err);
        }
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (email, password, totpCode) => {
    const payload = { email, password };
    if (totpCode) payload.totp_code = totpCode;
    const { data } = await api.post("/auth/login", payload);
    setUser({
      id: data.id,
      email: data.email,
      name: data.name,
      role: data.role,
      employee_id: data.employee_id,
      company_id: data.company_id,
      company: data.company,
      twofa_enabled: !!data.twofa_enabled,
      mof_approver: !!data.mof_approver,
      finance_officer: !!data.finance_officer,
    });
    return data;
  }, []);

  const applyAuth = useCallback((data) => {
    setUser({
      id: data.id,
      email: data.email,
      name: data.name,
      role: data.role,
      employee_id: data.employee_id,
      company_id: data.company_id,
      company: data.company,
      twofa_enabled: !!data.twofa_enabled,
      mof_approver: !!data.mof_approver,
      finance_officer: !!data.finance_officer,
    });
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) {
      console.warn("[Auth] logout request failed (proceeding to clear local session):", err?.message || err);
    }
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

  const value = useMemo(() => ({ user, loading, login, applyAuth, logout, refetch }), [user, loading, login, applyAuth, logout, refetch]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
