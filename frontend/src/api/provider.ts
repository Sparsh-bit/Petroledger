import { api } from "./client";

export interface ProviderStats {
  total_orgs: number;
  active_orgs: number;
  locked_orgs: number;
  mrr_inr: number;
}

export interface OrganizationSummary {
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

export interface OrganizationDetail {
  summary: OrganizationSummary;
  users: Array<{
    id: string;
    email: string;
    role: string;
    is_active: boolean;
    last_login: string | null;
  }>;
  pumps: Array<{ id: string; name: string; code: string | null; is_active: boolean }>;
}

export interface SubscriptionGroup {
  status: string;
  count: number;
  mrr_inr: number;
  organizations: OrganizationSummary[];
}

export interface SubscriptionsResponse {
  groups: SubscriptionGroup[];
  total_mrr_inr: number;
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

export const providerApi = {
  stats: () => api.get<ProviderStats>("/provider/stats").then((r) => r.data),
  subscriptions: () =>
    api.get<SubscriptionsResponse>("/provider/subscriptions").then((r) => r.data),
  organizations: () =>
    api
      .get<OrganizationSummary[]>("/provider/organizations")
      .then((r) => r.data),
  organization: (id: string) =>
    api
      .get<OrganizationDetail>(`/provider/organizations/${id}`)
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
  updateSubscription: (
    id: string,
    body: {
      plan?: string;
      status?: string;
      expires_at?: string | null;
      monthly_price_inr?: number;
    },
  ) =>
    api
      .patch<OrganizationSummary>(
        `/provider/organizations/${id}/subscription`,
        body,
      )
      .then((r) => r.data),
};
