import { api } from "./client";

export type AccessRequestStatus =
  | "NEW"
  | "CONTACTED"
  | "APPROVED"
  | "REJECTED";

export type PumpCountRange = "1" | "2-5" | "6-10" | "11-25" | "25+";

export interface AccessRequestPayload {
  full_name: string;
  email: string;
  phone: string;
  company: string;
  pump_count_range: PumpCountRange;
  city: string;
  state: string;
  message?: string;
  consent: boolean;
}

export interface AccessRequestSubmitResponse {
  id: string;
  status: AccessRequestStatus;
  message: string;
}

export interface AccessRequest {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  company: string;
  pump_count_range: string;
  city: string;
  state: string;
  message: string | null;
  status: AccessRequestStatus;
  provider_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccessRequestList {
  items: AccessRequest[];
  total: number;
  page: number;
  page_size: number;
}

export interface AccessRequestStats {
  new: number;
  contacted: number;
  approved: number;
  rejected: number;
  total: number;
}

export interface AccessRequestUpdate {
  status?: AccessRequestStatus;
  provider_notes?: string;
}

export const accessRequestsApi = {
  submit: (payload: AccessRequestPayload) =>
    api
      .post<AccessRequestSubmitResponse>("/access-requests", payload)
      .then((r) => r.data),

  // Provider
  list: (params?: {
    status?: AccessRequestStatus | "";
    search?: string;
    page?: number;
    page_size?: number;
  }) =>
    api
      .get<AccessRequestList>("/provider/access-requests", { params })
      .then((r) => r.data),

  detail: (id: string) =>
    api
      .get<AccessRequest>(`/provider/access-requests/${id}`)
      .then((r) => r.data),

  update: (id: string, body: AccessRequestUpdate) =>
    api
      .patch<AccessRequest>(`/provider/access-requests/${id}`, body)
      .then((r) => r.data),

  approve: (id: string, notes?: string) =>
    api
      .patch<AccessRequest>(`/provider/access-requests/${id}`, {
        status: "APPROVED",
        provider_notes: notes,
      })
      .then((r) => r.data),

  reject: (id: string, notes?: string) =>
    api
      .patch<AccessRequest>(`/provider/access-requests/${id}`, {
        status: "REJECTED",
        provider_notes: notes,
      })
      .then((r) => r.data),

  stats: () =>
    api
      .get<AccessRequestStats>("/provider/access-requests/stats")
      .then((r) => r.data),

  // Aliases matching the Stage 1 contract (§367)
  getAccessRequests: (params?: {
    status?: AccessRequestStatus | "";
    search?: string;
    page?: number;
    page_size?: number;
  }) =>
    api
      .get<AccessRequestList>("/provider/access-requests", { params })
      .then((r) => r.data),
  getAccessRequest: (id: string) =>
    api
      .get<AccessRequest>(`/provider/access-requests/${id}`)
      .then((r) => r.data),
  approveAccessRequest: (id: string, notes?: string) =>
    api
      .patch<AccessRequest>(`/provider/access-requests/${id}`, {
        status: "APPROVED",
        provider_notes: notes,
      })
      .then((r) => r.data),
  rejectAccessRequest: (id: string, notes?: string) =>
    api
      .patch<AccessRequest>(`/provider/access-requests/${id}`, {
        status: "REJECTED",
        provider_notes: notes,
      })
      .then((r) => r.data),
};
