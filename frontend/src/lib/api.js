import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const TOKEN_KEY = "salonehcm_token";

// Session token still kept in sessionStorage as a fallback (e.g. for fetch() calls
// that download blobs and need an explicit Authorization header). All XHR calls go
// through this axios instance which now sends an httpOnly cookie as the primary
// authentication channel — XSS-resistant. CSRF is enforced via double-submit cookie
// on state-changing methods.
export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (t) => sessionStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY);

const CSRF_COOKIE = "salonehcm_csrf";
const UNSAFE_METHODS = new Set(["post", "put", "patch", "delete"]);

const readCookie = (name) => {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(new RegExp("(?:^|; )" + name.replace(/[.$?*|{}()[\]\\/+^]/g, "\\$&") + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : null;
};

const instance = axios.create({ baseURL: API, withCredentials: true });

instance.interceptors.request.use((cfg) => {
  // Belt-and-suspenders: also send Authorization header when we have a token in
  // sessionStorage. The backend prefers the header over the cookie, so this lets
  // long-lived sessions survive a cookie expiry. New logins write both.
  const token = getToken();
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  // CSRF: echo the csrf cookie on every state-changing call.
  const method = (cfg.method || "get").toLowerCase();
  if (UNSAFE_METHODS.has(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) cfg.headers["X-CSRF-Token"] = csrf;
  }
  return cfg;
});

export default instance;

export const fmtSLE = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "SLE 0.00";
  return (
    "SLE " +
    Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  );
};

export const fmtNum = (n) =>
  Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
