import { api } from "./client";
import type { AuthUser } from "../store/auth";

export interface LoginPayload {
  email: string;
  password: string;
  pump_code?: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}

export async function loginRequest(
  payload: LoginPayload,
): Promise<LoginResponse> {
  const body: Record<string, unknown> = {
    email: payload.email,
    password: payload.password,
  };
  if (payload.pump_code) body.pump_code = payload.pump_code;
  const { data } = await api.post<LoginResponse>("/auth/login", body);
  return data;
}

export async function logoutRequest(): Promise<void> {
  try {
    await api.post("/auth/logout", {});
  } catch {
    /* ignore */
  }
}

export interface PasswordChangePayload {
  old_password: string;
  new_password: string;
}

export async function changePasswordRequest(
  payload: PasswordChangePayload,
): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>(
    "/auth/password-change",
    payload,
  );
  return data;
}

export interface MeResponse {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  tenant_id: string | null;
  last_login: string | null;
  created_at: string;
}

export async function meRequest(): Promise<MeResponse> {
  const { data } = await api.get<MeResponse>("/auth/me");
  return data;
}
