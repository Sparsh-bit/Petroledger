import { api } from "./client";

/* ----------------------------------------------------------------------
 * Shared types
 * -------------------------------------------------------------------- */

export interface Paged<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

/* ----------------------------------------------------------------------
 * Pumps
 * -------------------------------------------------------------------- */

export interface Nozzle {
  id: string;
  nozzle_number: number;
  fuel_type: string;
  product_name?: string | null;
}

export interface Pump {
  id: string;
  org_id: string;
  name: string;
  code?: string | null;
  location?: string | null;
  nozzle_count: number;
  is_active: boolean;
  is_deleted?: boolean;
  created_at: string;
  nozzles?: Nozzle[];
}

export interface PumpCreatePayload {
  // Optional — backend resolves to the caller's tenant's first org
  // (auto-creating a default one if none exists) when omitted.
  org_id?: string;
  name: string;
  location?: string;
  nozzle_count: number;
  nozzles?: Array<{ nozzle_number: number; fuel_type: string }>;
}

export interface PumpUpdatePayload {
  name?: string;
  location?: string;
  nozzle_count?: number;
  is_active?: boolean;
}

/* ----------------------------------------------------------------------
 * Workers
 * -------------------------------------------------------------------- */

export interface Worker {
  id: string;
  user_id: string;
  pump_id: string;
  employee_code: string;
  joined_date: string | null;
  is_active?: boolean;
  created_at?: string;
}

/** Two-step worker creation payload: the API client handles both calls. */
export interface WorkerCreatePayload {
  email: string;
  password: string;
  pump_id: string;
  employee_code: string;
  joined_date: string; // YYYY-MM-DD
  org_id?: string;
}

export interface WorkerUpdatePayload {
  pump_id?: string;
  employee_code?: string;
  is_active?: boolean;
}

/* ----------------------------------------------------------------------
 * Shifts / Reconciliation / Anomalies / Audit
 * -------------------------------------------------------------------- */

export interface Shift {
  id: string;
  pump_id: string;
  worker_id: string;
  start_time: string;
  end_time: string | null;
  status: string;
  slot?: string | null;
}

export interface ShiftListQuery {
  pump_id?: string;
  worker_id?: string;
  org_id?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export interface ReconciliationResult {
  id: string;
  shift_id: string;
  status: string;
  expected_cash: string | number;
  actual_cash: string | number;
  variance: string | number;
  confidence_score?: number | null;
  anomalies?: Array<Record<string, unknown>>;
  created_at: string;
}

export interface AnomalyFlag {
  id: string;
  site_id: string;
  shift_id: string | null;
  attendant_id?: string | null;
  flag_type: string;
  severity: string;
  description: string;
  amount?: string | number | null;
  is_resolved: boolean;
  resolved_at?: string | null;
  resolved_by?: string | null;
  resolution_note?: string | null;
  created_at: string;
}

export interface AuditLogItem {
  id: string;
  user_id: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
  before_state?: Record<string, unknown> | null;
  after_state?: Record<string, unknown> | null;
  ip_address?: string | null;
  org_id?: string | null;
  tenant_id?: string | null;
  created_at: string;
}

/* ----------------------------------------------------------------------
 * Analytics
 * -------------------------------------------------------------------- */

export interface VarianceTrendRow {
  date: string;
  total_variance: string;
  shortage_count: number;
  excess_count: number;
}

export interface GradeSalesRow {
  date: string;
  fuel_type: string;
  volume: string;
  amount: string;
}

export interface CashflowRow {
  date: string;
  cash: string;
  upi: string;
  card: string;
  fleet: string;
}

/* ----------------------------------------------------------------------
 * Inventory & Maintenance
 * -------------------------------------------------------------------- */

export interface Tank {
  id: string;
  org_id: string;
  tank_number: number;
  fuel_type: string;
  capacity_litres: string | number;
  current_level_litres: string | number;
  low_level_threshold: string | number;
  last_dip_reading_at: string | null;
  is_active: boolean;
}

export interface DipReadingPayload {
  reading_date: string; // YYYY-MM-DD
  reading_litres: number;
  temperature_celsius?: number;
  notes?: string;
}

export interface Downtime {
  id: string;
  pump_id: string;
  org_id: string;
  started_at: string;
  ended_at: string | null;
  reason_type: string;
  description: string | null;
  created_by_user_id: string | null;
  created_at: string;
}

export interface DowntimeStartPayload {
  pump_id: string;
  reason_type: string;
  description?: string;
  started_at?: string;
}

/* ----------------------------------------------------------------------
 * API
 * -------------------------------------------------------------------- */

export const adminApi = {
  // ── Pumps ─────────────────────────────────────────────────────────
  getPumps: (params?: { org_id?: string; page?: number; page_size?: number }) =>
    api
      .get<Paged<Pump>>("/pumps/", { params })
      .then((r) => r.data),
  getPump: (id: string) =>
    api.get<Pump>(`/pumps/${id}`).then((r) => r.data),
  createPump: (payload: PumpCreatePayload) =>
    api.post<Pump>("/pumps/", payload).then((r) => r.data),
  updatePump: (id: string, payload: PumpUpdatePayload) =>
    api.patch<Pump>(`/pumps/${id}`, payload).then((r) => r.data),
  deletePump: (id: string) =>
    api.delete(`/pumps/${id}`).then((r) => r.data),

  // ── Workers ───────────────────────────────────────────────────────
  getWorkers: (params?: {
    pump_id?: string;
    org_id?: string;
    page?: number;
    page_size?: number;
  }) =>
    api
      .get<Paged<Worker>>("/workers/", { params })
      .then((r) => r.data),

  /** Two-step worker creation: create user, then worker profile. */
  createWorker: async (payload: WorkerCreatePayload) => {
    // Step 1: create user with role=worker
    const userRes = await api.post<{
      id: string;
      email: string;
    }>("/users/", {
      email: payload.email,
      password: payload.password,
      role: "worker",
      org_id: payload.org_id,
    });
    // Step 2: create worker profile linked to that user
    return api
      .post<Worker>("/workers/", {
        user_id: userRes.data.id,
        pump_id: payload.pump_id,
        employee_code: payload.employee_code,
        joined_date: payload.joined_date,
      })
      .then((r) => r.data);
  },
  updateWorker: (id: string, payload: WorkerUpdatePayload) =>
    api.patch<Worker>(`/workers/${id}`, payload).then((r) => r.data),
  deleteWorker: (id: string) =>
    api.delete(`/workers/${id}`).then((r) => r.data),

  // ── Shifts ────────────────────────────────────────────────────────
  getShifts: (params?: ShiftListQuery) =>
    api
      .get<Paged<Shift>>("/shifts/", { params })
      .then((r) => r.data),
  getShift: (id: string) =>
    api.get<Shift>(`/shifts/${id}`).then((r) => r.data),

  // ── Reconciliation ────────────────────────────────────────────────
  getShiftReconciliation: (shiftId: string) =>
    api
      .get<ReconciliationResult>(`/reconciliation/shifts/${shiftId}`)
      .then((r) => r.data),
  getReconciliationQueue: (params?: {
    org_id?: string;
    page?: number;
    page_size?: number;
  }) =>
    api
      .get<Paged<Shift>>("/shifts/", {
        params: { status: "COMPLETED", ...params },
      })
      .then((r) => r.data),
  runReconciliation: (shiftId: string, actualCash: number) =>
    api
      .post<ReconciliationResult>(`/reconciliation/shifts/${shiftId}/run`, {
        actual_cash: actualCash,
      })
      .then((r) => r.data),

  // ── Anomalies ─────────────────────────────────────────────────────
  getAnomalies: (params: {
    site_id?: string;
    shift_id?: string;
    is_resolved?: boolean;
    severity?: string;
    flag_type?: string;
    page?: number;
    page_size?: number;
  }) =>
    api
      .get<Paged<AnomalyFlag>>("/anomaly-flags/", { params })
      .then((r) => r.data),
  getAnomaly: (id: string) =>
    api.get<AnomalyFlag>(`/anomaly-flags/${id}`).then((r) => r.data),
  resolveAnomaly: (id: string, resolutionNote: string) =>
    api
      .patch<AnomalyFlag>(`/anomaly-flags/${id}/resolve`, {
        resolution_note: resolutionNote,
      })
      .then((r) => r.data),

  // ── Audit Logs ────────────────────────────────────────────────────
  getAuditLogs: (params?: {
    org_id?: string;
    entity_type?: string;
    action?: string;
    user_id?: string;
    start_date?: string;
    end_date?: string;
    page?: number;
    page_size?: number;
  }) =>
    api
      .get<Paged<AuditLogItem>>("/audit-logs/", { params })
      .then((r) => r.data),

  // ── Analytics ─────────────────────────────────────────────────────
  getAnalytics: (params: { org_id: string; days?: number }) =>
    Promise.all([
      api.get<VarianceTrendRow[]>("/analytics/variance-trend", {
        params: { org_id: params.org_id, days: params.days ?? 30 },
      }),
      api.get<GradeSalesRow[]>("/analytics/grade-sales", {
        params: { org_id: params.org_id, days: params.days ?? 30 },
      }),
      api.get<CashflowRow[]>("/analytics/daily-cashflow", {
        params: { org_id: params.org_id, days: params.days ?? 30 },
      }),
    ]).then(([variance, grades, cashflow]) => ({
      variance: variance.data,
      grades: grades.data,
      cashflow: cashflow.data,
    })),

  getVarianceTrend: (org_id: string, days = 30) =>
    api
      .get<VarianceTrendRow[]>("/analytics/variance-trend", {
        params: { org_id, days },
      })
      .then((r) => r.data),

  // ── Inventory (Fuel Tanks) ────────────────────────────────────────
  getTanks: (params?: { org_id?: string }) =>
    api
      .get<Paged<Tank>>("/inventory/tanks", { params })
      .then((r) => r.data),
  createTank: (payload: {
    org_id: string;
    tank_number: number;
    fuel_type: string;
    capacity_litres: number;
    low_level_threshold?: number;
  }) =>
    api.post<Tank>("/inventory/tanks", payload).then((r) => r.data),
  createDipReading: (tankId: string, payload: DipReadingPayload) =>
    api
      .post(`/inventory/tanks/${tankId}/dip-readings`, payload)
      .then((r) => r.data),

  // ── Maintenance (Pump Downtime) ───────────────────────────────────
  getDowntimes: (params?: {
    org_id?: string;
    pump_id?: string;
    open_only?: boolean;
    page?: number;
    page_size?: number;
  }) =>
    api
      .get<Paged<Downtime>>("/maintenance/downtime", { params })
      .then((r) => r.data),
  startDowntime: (payload: DowntimeStartPayload) =>
    api.post<Downtime>("/maintenance/downtime/start", payload).then((r) => r.data),
  endDowntime: (id: string, endedAt?: string) =>
    api
      .post<Downtime>(`/maintenance/downtime/${id}/end`, {
        ended_at: endedAt,
      })
      .then((r) => r.data),
};
