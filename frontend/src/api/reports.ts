import { api } from "./client";

/** Shared type — matches the backend `format` query parameter. */
export type ReportFormat = "pdf" | "excel";

/** Trigger a browser download for an arbitrary Blob with a filename. */
function triggerDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  a.remove();
}

export const reportsApi = {
  /** Fetch a shift PDF report as a Blob. */
  generateShiftReport: async (shiftId: string): Promise<Blob> => {
    const res = await api.get(`/reports/shift/${shiftId}`, {
      responseType: "blob",
    });
    return res.data as Blob;
  },

  /** Fetch a daily report (PDF or Excel) as a Blob. */
  generateDailyReport: async (params: {
    site_id: string;
    report_date: string; // YYYY-MM-DD
    format?: ReportFormat;
  }): Promise<Blob> => {
    const res = await api.get(`/reports/daily`, {
      params: {
        site_id: params.site_id,
        report_date: params.report_date,
        format: params.format ?? "pdf",
      },
      responseType: "blob",
    });
    return res.data as Blob;
  },

  /** Download a shift report PDF and trigger browser save. */
  downloadShiftReport: async (shiftId: string): Promise<void> => {
    const blob = await reportsApi.generateShiftReport(shiftId);
    triggerDownload(blob, `shift-${shiftId.slice(0, 8)}.pdf`);
  },

  /** Download a daily report (PDF or Excel) and trigger browser save. */
  downloadDailyReport: async (params: {
    site_id: string;
    report_date: string;
    format?: ReportFormat;
  }): Promise<void> => {
    const fmt = params.format ?? "pdf";
    const blob = await reportsApi.generateDailyReport(params);
    const ext = fmt === "excel" ? "xlsx" : "pdf";
    triggerDownload(blob, `daily-${params.report_date}.${ext}`);
  },
};
