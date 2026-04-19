import { api } from "./client";
import type { AuthUser } from "../store/auth";

export interface LoginPayload {
  email: string;
  password: string;
  pump_code?: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginResponse extends TokenPair {
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

export interface RegisterPayload {
  tenant_name: string;
  owner_name: string;
  owner_phone: string;
  owner_email: string;
  password: string;
}

export interface RegisterResponse {
  access_token: string;
  refresh_token: string;
  tenant_id: string;
  user_id: string;
}

export async function registerRequest(
  payload: RegisterPayload,
): Promise<RegisterResponse> {
  const { data } = await api.post<RegisterResponse>("/auth/register", payload);
  return data;
}

export async function refreshTokenRequest(
  refresh_token: string,
): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>("/auth/refresh", {
    refresh_token,
  });
  return data;
}

export async function logoutRequest(): Promise<void> {
  try {
    await api.post("/auth/logout", {});
  } catch {
    /* ignore logout failures — local state is cleared regardless */
  }
}

export async function forgotPasswordRequest(
  email: string,
): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>(
    "/auth/password-reset/request",
    { email },
  );
  return data;
}

export async function resetPasswordRequest(
  token: string,
  new_password: string,
): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>(
    "/auth/password-reset/confirm",
    { token, new_password },
  );
  return data;
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

export async function googleAuthRequest(
  id_token: string,
): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>("/auth/google", { id_token });
  return data;
}

export async function sendOtpRequest(
  phone_number: string,
): Promise<{ message: string }> {
  const { data } = await api.post<{ message: string }>("/auth/otp/send", {
    phone_number,
  });
  return data;
}

export async function verifyOtpRequest(
  phone_number: string,
  otp: string,
): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>("/auth/otp/verify", {
    phone_number,
    otp,
  });
  return data;
}

export interface MeResponse {
  id: string;
  email: string;
  phone: string | null;
  role: string;
  is_active: boolean;
  org_id: string | null;
  last_login: string | null;
  created_at: string;
  updated_at: string;
}

export async function meRequest(): Promise<MeResponse> {
  const { data } = await api.get<MeResponse>("/auth/me");
  return data;
}

export const authApi = {
  login: loginRequest,
  register: registerRequest,
  refresh: refreshTokenRequest,
  logout: logoutRequest,
  forgotPassword: forgotPasswordRequest,
  resetPassword: resetPasswordRequest,
  changePassword: changePasswordRequest,
  googleAuth: googleAuthRequest,
  sendOtp: sendOtpRequest,
  verifyOtp: verifyOtpRequest,
  me: meRequest,
};
