import { api } from "./client";

export type IngestionKind = "upi-csv" | "pos-slip" | "pump-logs";

export interface IngestionJobResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface IngestionResultRow {
  row_number: number;
  status: string;
  message?: string;
  data?: Record<string, unknown>;
}

export interface IngestionResult {
  total_rows: number;
  valid_rows: number;
  duplicate_rows: number;
  invalid_rows: number;
  sample: IngestionResultRow[];
}

export interface JobStatusResponse {
  job_id: string;
  status: string;
  progress: number;
  result: IngestionResult | null;
  error: string | null;
  created_at?: string;
}

function makeForm(
  file: File,
  extra: Record<string, string>,
): FormData {
  const fd = new FormData();
  fd.append("file", file);
  for (const [k, v] of Object.entries(extra)) fd.append(k, v);
  return fd;
}

export const dataIngestionApi = {
  /**
   * Upload an ingestion file (UPI CSV, POS slip, or pump log) for
   * background processing. The server responds 202 with a job_id
   * that must be polled via getIngestionStatus.
   */
  uploadFile: async (
    kind: IngestionKind,
    file: File,
    context: { shift_id: string; pump_id?: string },
  ): Promise<IngestionJobResponse> => {
    const extra: Record<string, string> = { shift_id: context.shift_id };
    if (kind === "pump-logs") {
      if (!context.pump_id) {
        throw new Error("pump_id is required for pump-logs uploads.");
      }
      extra.pump_id = context.pump_id;
    }
    const res = await api.post<IngestionJobResponse>(
      `/data-ingestion/${kind}`,
      makeForm(file, extra),
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return res.data;
  },

  getIngestionStatus: (job_id: string) =>
    api
      .get<JobStatusResponse>(`/data-ingestion/status/${job_id}`)
      .then((r) => r.data),

  /**
   * Returns the result payload of a completed job, or null if still
   * in-flight. Convenience on top of getIngestionStatus.
   */
  getIngestionResults: async (
    job_id: string,
  ): Promise<IngestionResult | null> => {
    const s = await dataIngestionApi.getIngestionStatus(job_id);
    return s.result;
  },

  /** Confirm an ingestion preview → commit rows to the DB. */
  confirmIngestion: (job_id: string) =>
    api
      .post<{ job_id: string; committed: number }>(
        `/data-ingestion/${job_id}/confirm`,
      )
      .then((r) => r.data),

  /** Revert an ingestion — soft-delete the rows written by this job. */
  revertIngestion: (job_id: string) =>
    api
      .post<{ job_id: string; reverted: number }>(
        `/data-ingestion/${job_id}/revert`,
      )
      .then((r) => r.data),
};
