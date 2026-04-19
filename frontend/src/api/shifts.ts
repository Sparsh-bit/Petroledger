import { api } from "./client";
import type { Shift, Paged } from "./admin";

export type { Shift, Paged };

export interface ShiftCreatePayload {
  pump_id: string;
  worker_id: string;
  start_time: string;
  slot?: string;
}

export interface ShiftUpdatePayload {
  end_time?: string;
  status?: string;
}

export interface MeterReading {
  id: string;
  shift_id: string;
  nozzle_id: string;
  opening_reading: string | number | null;
  closing_reading: string | number | null;
  created_at: string;
}

export interface CashEntry {
  id: string;
  shift_id: string;
  physical_cash?: string | number;
  amount?: string | number;
  denominations?: Record<string, number>;
  entry_type?: string;
  created_at: string;
}

export interface PosTransaction {
  id: string;
  shift_id: string;
  amount: string | number;
  entry_method?: string;
  fuel_type?: string;
  created_at: string;
}

export interface UpiTransaction {
  id: string;
  shift_id: string;
  amount: string | number;
  upi_ref?: string;
  created_at: string;
}

export const shiftsApi = {
  /** Start a shift for a worker at a pump. */
  startShift: (payload: ShiftCreatePayload) =>
    api.post<Shift>("/shifts/", payload).then((r) => r.data),

  /** Close/complete a shift by setting end_time + status. */
  closeShift: (shiftId: string, payload: ShiftUpdatePayload) =>
    api.patch<Shift>(`/shifts/${shiftId}`, payload).then((r) => r.data),

  /** List shifts with filters. */
  list: (params?: {
    pump_id?: string;
    worker_id?: string;
    org_id?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }) =>
    api.get<Paged<Shift>>("/shifts/", { params }).then((r) => r.data),

  /** Fetch one shift. */
  get: (id: string) => api.get<Shift>(`/shifts/${id}`).then((r) => r.data),

  // ── Meter readings ─────────────────────────────────────────────────
  getMeterReadings: (shiftId: string) =>
    api
      .get<Paged<MeterReading> | MeterReading[]>(`/meter-readings/`, {
        params: { shift_id: shiftId },
      })
      .then((r) => r.data),

  saveMeterReadings: (
    shiftId: string,
    payload: { nozzle_id: string; closing_reading: number },
  ) =>
    api
      .post<MeterReading>(`/meter-readings/shifts/${shiftId}/manual`, payload)
      .then((r) => r.data),

  // ── Cash entries ──────────────────────────────────────────────────
  getCashEntries: (params?: { shift_id?: string; page?: number }) =>
    api
      .get<Paged<CashEntry> | CashEntry[]>("/cash-entries/", { params })
      .then((r) => r.data),

  saveCashEntry: (payload: {
    shift_id: string;
    physical_cash: number;
    denominations?: Record<string, number>;
  }) =>
    api.post<CashEntry>("/cash-entries/", payload).then((r) => r.data),

  // ── POS / UPI transactions ────────────────────────────────────────
  getPosTransactions: (params?: { shift_id?: string; page?: number }) =>
    api
      .get<Paged<PosTransaction> | PosTransaction[]>(
        "/pos-batch-settlements/",
        { params },
      )
      .then((r) => r.data),

  getUpiTransactions: (params?: { shift_id?: string; page?: number }) =>
    api
      .get<Paged<UpiTransaction> | UpiTransaction[]>("/upi-transactions/", {
        params,
      })
      .then((r) => r.data),
};
