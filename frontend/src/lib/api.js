import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export // Browser requests use the HttpOnly auth cookie and double-submit CSRF token.
// Do not persist or attach JavaScript-readable bearer tokens in this client.

const CSRF_COOKIE = "salonehcm_csrf";
const UNSAFE_METHODS = new Set(["post", "put", "patch", "delete"]);

const readCookie = (name) => {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(new RegExp("(?:^|; )" + name.replace(/[.$?*|{}()[\]\\/+^]/g, "\\$&") + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : null;
};

const instance = axios.create({ baseURL: API, withCredentials: true });

instance.interceptors.request.use((cfg) => {
  // Authenticate with the HttpOnly cookie. CSRF: echo the csrf cookie on
  // every state-changing call.
  const method = (cfg.method || "get").toLowerCase();
  if (UNSAFE_METHODS.has(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) cfg.headers["X-CSRF-Token"] = csrf;
  }
  return cfg;
});

export default instance;

// Normalize FastAPI/Pydantic error payloads: 422 responses carry `detail` as an
// array of error objects, which crashes React when passed straight to a toast.
// Coerce ARRAYS to a readable string; leave plain-object details (e.g. auth's
// {code, message} for totp_required / invite_expired) intact — Login handles those.
instance.interceptors.response.use(
  (r) => r,
  (error) => {
    const d = error?.response?.data?.detail;
    if (Array.isArray(d)) {
      error.response.data.detail = d.map((x) => (x && x.msg) || JSON.stringify(x)).join("; ");
    }
    return Promise.reject(error);
  }
);

/**
 * Trigger a file download by GETting a binary blob from the API and clicking
 * a synthetic <a download> link. Uses the same axios instance so cookies +
 * Cookies + CSRF are attached automatically — no raw fetch().
 */
export const downloadBlob = async (path, filename) => {
  const res = await instance.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export const fmtSLE = (n) => {
  if (n === null || n === undefined || isNaN(n)) return "SLE 0.00";
  return (
    "SLE " +
    Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  );
};

export const fmtNum = (n) =>
  Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
