import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const TOKEN_KEY = "salonehcm_token";

// Use sessionStorage instead of localStorage — token cleared on tab close, smaller XSS surface
export const getToken = () => sessionStorage.getItem(TOKEN_KEY);
export const setToken = (t) => sessionStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => sessionStorage.removeItem(TOKEN_KEY);

const instance = axios.create({ baseURL: API, withCredentials: false });

instance.interceptors.request.use((cfg) => {
  const token = getToken();
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
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
