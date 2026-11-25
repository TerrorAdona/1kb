import { api, ensureCsrfCookie } from "../../shared/api/client";
import type { User } from "../../shared/types/api";

export interface LoginResponse {
  access: string;
  user: User;
}

export async function registerAccount(payload: {
  email: string;
  display_name: string;
  password: string;
}) {
  const { data } = await api.post<User>("/auth/register/", payload);
  return data;
}

export async function loginAccount(email: string, password: string) {
  await ensureCsrfCookie();
  const { data } = await api.post<LoginResponse>("/auth/login/", {
    email,
    password,
  });
  return data;
}

export async function getCurrentUser() {
  const { data } = await api.get<User>("/auth/me/");
  return data;
}

export async function updateCurrentUser(display_name: string) {
  const { data } = await api.patch<User>("/auth/me/", { display_name });
  return data;
}

export async function logoutAccount() {
  await ensureCsrfCookie();
  await api.post("/auth/logout/", {});
}
