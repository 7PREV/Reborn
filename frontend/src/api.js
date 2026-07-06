import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
export const API = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export function collectSecurityTokens() {
  const out = {
    csrfToken: "",
    recaptchaToken: "",
    turnstileToken: "",
  };

  try {
    out.csrfToken =
      document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ||
      window.__CSRF_TOKEN__ ||
      "";
  } catch {
    out.csrfToken = "";
  }

  try {
    if (window.turnstile?.getResponse) {
      out.turnstileToken = window.turnstile.getResponse() || "";
    }
  } catch {
    out.turnstileToken = window.__TURNSTILE_TOKEN__ || "";
  }

  try {
    if (window.grecaptcha?.getResponse) {
      out.recaptchaToken = window.grecaptcha.getResponse() || "";
    }
  } catch {
    out.recaptchaToken = window.__RECAPTCHA_TOKEN__ || "";
  }

  return out;
}

api.interceptors.request.use((config) => {
  const tokens = collectSecurityTokens();
  config.headers = config.headers || {};
  if (tokens.csrfToken) config.headers["X-CSRF-Token"] = tokens.csrfToken;
  if (tokens.recaptchaToken) config.headers["X-Recaptcha-Token"] = tokens.recaptchaToken;
  if (tokens.turnstileToken) config.headers["CF-Turnstile-Response"] = tokens.turnstileToken;
  return config;
});

let isRefreshing = false;
let refreshQueue = [];

function flushRefreshQueue(error) {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve();
  });
  refreshQueue = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error?.config || {};
    const status = error?.response?.status;
    const url = String(original?.url || "");
    const isAuthLoginFlow =
      url.includes("/auth/login") ||
      url.includes("/auth/register") ||
      url.includes("/auth/forgot-password");

    if (status !== 401 || original._retry || url.includes("/auth/refresh") || isAuthLoginFlow) {
      return Promise.reject(error);
    }

    original._retry = true;

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        refreshQueue.push({
          resolve: async () => {
            try {
              resolve(api(original));
            } catch (e) {
              reject(e);
            }
          },
          reject,
        });
      });
    }

    isRefreshing = true;
    try {
      await api.post("/auth/refresh");
      flushRefreshQueue(null);
      return api(original);
    } catch (refreshError) {
      flushRefreshQueue(refreshError);
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export default api;

export const authRefresh = () => api.post("/auth/refresh");
export const authRevoke = (session_id) => api.post("/auth/revoke", { session_id });
export const authSessions = () => api.get("/auth/sessions");
export const billingSubscription = () => api.get("/billing/subscription");
export const billingCheckout = (payload) => api.post("/billing/checkout", payload);
export const notificationsList = (params = {}) => api.get("/notifications", { params });
export const notificationsRead = (payload) => api.post("/notifications/read", payload);
export const adminAuditLog = (params = {}) => api.get("/admin/audit-log", { params });
export const apiMetrics = () => api.get("/metrics");

export function formatApiErrorDetail(detail) {
  if (detail == null) return "حدث خطأ، حاول مرة أخرى.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}
