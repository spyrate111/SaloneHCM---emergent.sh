import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const instance = axios.create({ baseURL: API, withCredentials: false });

instance.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("salonehcm_token");
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
