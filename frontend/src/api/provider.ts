import { api } from "./client";

export interface ProviderStats {
  total_orgs: number;
  active_orgs: number;
  locked_orgs: number;
  mrr_inr: number;
}

/**
 * Tenant summary — the backend exposes this as `organizations` today, but
 * semantically it is a tenant record (1 tenant = 1 dealer). The Stage 2
 * page rename will migrate the UI to `/provider/tenants`.
 */
export interface TenantSummary {
  tenant_id: string;
  name: string;
  owner_email: string;
  owner_phone: string;
  subscription_plan: string;
  subscription_status: string;
  subscription_expires_at: string | null;
  monthly_price_inr: number;
  is_active: boolean;
  is_locked: boolean;
  user_count: number;
  pump_count: number;
  org_count: number;
  created_at: string;
}

/** @deprecated — kept as an alias for Stage 1 compatibility. Use TenantSummary. */
export type OrganizationSummary = TenantSummary;

export interface TenantDetail {
  summary: TenantSummary;
  users: Array<{
    id: string;
    email: string;
    role: string;
    is_active: boolean;
    last_login: string | null;
  }>;
  pumps: Array<{
    id: string;
    name: string;
    code: string | null;
    is_active: boolean;
  }>;
}

/** @deprecated — alias retained for Stage 1 compatibility. */
export type OrganizationDetail = TenantDetail;

export interface SubscriptionGroup {
  status: string;
  count: number;
  mrr_inr: number;
  organizations: TenantSummary[];
}

export interface SubscriptionsResponse {
  groups: SubscriptionGroup[];
  total_mrr_inr: number;
}

export interface SubscriptionUpdatePayload {
  plan?: string;
  status?: string;
  expires_at?: string | null;
  monthly_price_inr?: number;
}

export interface ProviderUserItem {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  tenant_id: string | null;
  tenant_name: string | null;
  last_login: string | null;
  created_at: string;
}

export interface ProviderUsersResponse {
  items: ProviderUserItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProviderSettings {
  maintenance_mode?: boolean;
  default_plan?: string;
  rate_limit_threshold?: number;
  smtp_configured?: boolean;
}

export interface TenantFeatureItem {
  id: number;
  key: string;
  name: string;
  module: string;
  is_core: boolean;
  plan_enabled: boolean;
  override_enabled: boolean | null;
  effective: boolean;
  source: "core" | "plan" | "override" | "none";
}

export interface PaymentConfigResponse {
  configured: boolean;
  gateway: string;
  key_id_masked: string | null;
  has_webhook_secret: boolean;
  is_enabled: boolean;
}

export const providerApi = {
  // ── Tenants (listing / detail) ────────────────────────────────────
  getTenants: (): Promise<TenantSummary[]> =>
    api.get<TenantSummary[]>("/provider/organizations").then((r) => r.data),
  getTenant: (id: string): Promise<TenantDetail> =>
    api
      .get<TenantDetail>(`/provider/organizations/${id}`)
      .then((r) => r.data),

  /** Create a tenant + owner user + first organization + first pump in one call.
   *  The returned tenant's pump_code is the login key its staff will type
   *  alongside their email + password. */
  createTenant: (payload: {
    tenant_name: string;
    owner_name: string;
    owner_email: string;
    owner_phone: string;
    password: string;
    pump_code?: string;
    org_name?: string;
    pump_name?: string;
    subscription_plan?: "BASIC" | "PRO" | "ENTERPRISE";
    monthly_price_inr?: number;
  }): Promise<TenantSummary> =>
    api
      .post<TenantSummary>("/provider/organizations", payload)
      .then((r) => r.data),

  /** Permanently delete a tenant and every record it owns. The caller
   *  must echo the tenant's name in confirm_name — there is no undo. */
  deleteTenant: (
    id: string,
    confirm_name: string,
  ): Promise<{ message: string }> =>
    api
      .delete<{ message: string }>(`/provider/organizations/${id}`, {
        data: { confirm_name },
      })
      .then((r) => r.data),

  updateTenant: (
    id: string,
    payload: Partial<Pick<TenantSummary, "name" | "owner_phone">>,
  ): Promise<TenantSummary> =>
    api
      .patch<TenantSummary>(`/provider/organizations/${id}`, payload)
      .then((r) => r.data),

  lockTenant: (id: string): Promise<{ message: string }> =>
    api
      .post<{ message: string }>(`/provider/organizations/${id}/lock`)
      .then((r) => r.data),

  unlockTenant: (id: string): Promise<{ message: string }> =>
    api
      .post<{ message: string }>(`/provider/organizations/${id}/unlock`)
      .then((r) => r.data),

  // ── Subscriptions ─────────────────────────────────────────────────
  getSubscriptions: (): Promise<SubscriptionsResponse> =>
    api
      .get<SubscriptionsResponse>("/provider/subscriptions")
      .then((r) => r.data),

  updateSubscription: (
    id: string,
    body: SubscriptionUpdatePayload,
  ): Promise<TenantSummary> =>
    api
      .patch<TenantSummary>(`/provider/organizations/${id}/subscription`, body)
      .then((r) => r.data),

  // ── Users (cross-tenant) ──────────────────────────────────────────
  getUsers: (params?: {
    role?: string;
    tenant_id?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<ProviderUsersResponse> =>
    api
      .get<ProviderUsersResponse>("/provider/users", { params })
      .then((r) => r.data),

  deactivateUser: (id: string) =>
    api.patch(`/users/${id}/deactivate`).then((r) => r.data),

  reactivateUser: (id: string) =>
    api.patch(`/users/${id}/reactivate`).then((r) => r.data),

  // ── KPIs ──────────────────────────────────────────────────────────
  getProviderKpis: (): Promise<ProviderStats> =>
    api.get<ProviderStats>("/provider/stats").then((r) => r.data),

  // ── Settings (best-effort — endpoint may be Stage 2) ──────────────
  getProviderSettings: (): Promise<ProviderSettings> =>
    api
      .get<ProviderSettings>("/provider/settings")
      .then((r) => r.data)
      .catch(() => ({})),

  updateProviderSettings: (
    body: ProviderSettings,
  ): Promise<ProviderSettings> =>
    api
      .patch<ProviderSettings>("/provider/settings", body)
      .then((r) => r.data),

  // ── Legacy aliases (kept for the existing pages in /provider/) ─────
  stats: (): Promise<ProviderStats> =>
    api.get<ProviderStats>("/provider/stats").then((r) => r.data),
  subscriptions: (): Promise<SubscriptionsResponse> =>
    api
      .get<SubscriptionsResponse>("/provider/subscriptions")
      .then((r) => r.data),
  organizations: (): Promise<TenantSummary[]> =>
    api.get<TenantSummary[]>("/provider/organizations").then((r) => r.data),
  organization: (id: string): Promise<TenantDetail> =>
    api
      .get<TenantDetail>(`/provider/organizations/${id}`)
      .then((r) => r.data),
  lock: (id: string) =>
    api.post(`/provider/organizations/${id}/lock`).then((r) => r.data),
  unlock: (id: string) =>
    api.post(`/provider/organizations/${id}/unlock`).then((r) => r.data),
  users: (params?: {
    role?: string;
    tenant_id?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) =>
    api
      .get<ProviderUsersResponse>("/provider/users", { params })
      .then((r) => r.data),
};
