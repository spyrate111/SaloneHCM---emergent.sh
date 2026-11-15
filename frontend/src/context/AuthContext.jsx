import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import api, { getToken, setToken, clearToken } from "../lib/api";
import { clearOfflinePayslips } from "../lib/offlinePayslips";

const AuthCtx = createContext(null);
const OFFLINE_USER_KEY = "salonehcm_offline_session_user";
const OFFLINE_USER_TTL_MS = 7 * 24 * 60 * 60 * 1000;

function offlineUserSnapshot(user) {
  if (!user?.id) return null;
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    first_name: user.first_name,
    last_name: user.last_name,
    role: user.role,
    employee_id: user.employee_id,
    company_id: user.company_id,
    company: user.company ? {
      id: user.company.id,
      name: user.company.name,
      features: Array.isArray(user.company.features) ? user.company.features : [],
    } : null,
    twofa_enabled: !!user.twofa_enabled,
    mof_approver: !!user.mof_approver,
    finance_officer: !!user.finance_officer,
  };
}

function saveOfflineUser(user) {
  const snapshot = offlineUserSnapshot(user);
  if (!snapshot) return;
  try {
    sessionStorage.setItem(OFFLINE_USER_KEY, JSON.stringify({ user: snapshot, saved_at: Date.now() }));
  } catch { /* session restoration remains online-only if storage is unavailable */ }
}

function readOfflineUser() {
  try {
    const cached = JSON.parse(sessionStorage.getItem(OFFLINE_USER_KEY) || "null");
    if (!cached?.user?.id || !Number.isFinite(cached.saved_at) || Date.now() - cached.saved_at > OFFLINE_USER_TTL_MS) return null;
    return offlineUserSnapshot(cached.user);
  } catch {
    return null;
  }
}

function clearOfflineUser() {
  try { sessionStorage.removeItem(OFFLINE_USER_KEY); } catch { /* noop */ }
}

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
      .then((r) => {
        saveOfflineUser(r.data);
        setUser(r.data);
      })
      .catch((err) => {
        console.warn("[Auth] session restore failed:", err?.message || err);
        const cachedUser = readOfflineUser();
        const mayRestoreOffline = cachedUser && (!err?.response || err.response.status >= 500);
        if (mayRestoreOffline && getToken()) {
          setUser(cachedUser);
          return;
        }
        clearToken();
        clearOfflineUser();
        if (cachedUser?.id) {
          void clearOfflinePayslips(cachedUser.id).catch(() => {});
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password, totpCode) => {
    const payload = { email, password };
    if (totpCode) payload.totp_code = totpCode;
    const { data } = await api.post("/auth/login", payload);
    const previousUser = readOfflineUser();
    if (previousUser && String(previousUser.id) !== String(data.id)) {
      void clearOfflinePayslips(previousUser.id).catch(() => {});
    }
    setToken(data.token);
    const nextUser = {
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
    };
    saveOfflineUser(nextUser);
    setUser(nextUser);
    return data;
  }, []);

  const applyAuth = useCallback((data) => {
    const previousUser = readOfflineUser();
    if (previousUser && String(previousUser.id) !== String(data.id)) {
      void clearOfflinePayslips(previousUser.id).catch(() => {});
    }
    if (data?.token) setToken(data.token);
    const nextUser = {
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
    };
    saveOfflineUser(nextUser);
    setUser(nextUser);
  }, []);

  const logout = useCallback(() => {
    const accountId = user?.id;
    const token = getToken();
    const request = api.post(
      "/auth/logout",
      {},
      { headers: token ? { Authorization: `Bearer ${token}` } : {} },
    ).catch((err) => {
      console.warn("[Auth] logout request failed (local session was cleared):", err?.message || err);
    });
    clearToken();
    clearOfflineUser();
    setUser(null);
    if (accountId) {
      void clearOfflinePayslips(accountId).catch(() => {});
    }
    return request;
  }, [user?.id]);

  const refetch = useCallback(async () => {
    try {
      const r = await api.get("/auth/me");
      saveOfflineUser(r.data);
      setUser(r.data);
      return r.data;
    } catch (err) {
      console.warn("[Auth] refetch failed:", err?.message || err);
      if ([401, 403].includes(err?.response?.status)) {
        clearToken();
        clearOfflineUser();
        setUser(null);
        if (user?.id) {
          void clearOfflinePayslips(user.id).catch(() => {});
        }
      }
      return null;
    }
  }, [user?.id]);

  useEffect(() => {
    if (!user) return undefined;
    const refreshOnReconnect = () => { void refetch(); };
    window.addEventListener("online", refreshOnReconnect);
    return () => window.removeEventListener("online", refreshOnReconnect);
  }, [user?.id, refetch]);

  const value = useMemo(() => ({ user, loading, login, applyAuth, logout, refetch }), [user, loading, login, applyAuth, logout, refetch]);
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
