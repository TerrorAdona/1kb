import axios, { type InternalAxiosRequestConfig } from "axios";
import { getAccessToken, setAccessToken } from "./tokenMemory";

const baseURL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
  timeout: 12_000,
});

type RetriableConfig = InternalAxiosRequestConfig & { _authRetry?: boolean };

function readCookie(name: string) {
  if (typeof document === "undefined") return null;
  const cookie = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${name}=`));
  return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : null;
}

export async function ensureCsrfCookie() {
  if (!readCookie("csrftoken")) {
    await api.get("/auth/csrf/");
  }
}

let refreshPromise: Promise<string> | null = null;

export async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      await ensureCsrfCookie();
      const { data } = await api.post<{ access: string }>("/auth/refresh/", {});
      setAccessToken(data.access);
      return data.access;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.set("Authorization", `Bearer ${token}`);

  const csrfToken = readCookie("csrftoken");
  if (csrfToken && ["post", "put", "patch", "delete"].includes(config.method ?? "")) {
    config.headers.set("X-CSRFToken", csrfToken);
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || error.response?.status !== 401) {
      return Promise.reject(error);
    }
    const request = error.config as RetriableConfig | undefined;
    const url = request?.url ?? "";
    const isAuthEndpoint = ["/auth/login/", "/auth/refresh/", "/auth/register/", "/auth/logout/"]
      .some((path) => url.includes(path));
    if (!request || request._authRetry || isAuthEndpoint) {
      return Promise.reject(error);
    }

    request._authRetry = true;
    try {
      await refreshAccessToken();
      return api(request);
    } catch {
      setAccessToken(null);
      return Promise.reject(error);
    }
  },
);
