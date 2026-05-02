/**
 * Extract a human-readable error message from an unknown thrown value.
 *
 * Handles:
 *  - FastAPI 422 validation errors where `detail` is an array of
 *    `{type, loc, msg, input}` objects — previously these were returned
 *    as-is and react-hot-toast tried to render the array as React children,
 *    triggering React error #31.
 *  - FastAPI 4xx/5xx errors where `detail` is a plain string.
 *  - Generic JS Error objects.
 */
export function errMsg(err: unknown, fallback: string): string {
  const e = err as {
    response?: { data?: { detail?: unknown } };
    message?: string;
  };
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    // FastAPI 422: [{type, loc, msg, input}]
    const first = detail[0] as { msg?: string; message?: string };
    const msg = first?.msg || first?.message;
    if (typeof msg === "string" && msg) return msg;
  }
  return (typeof e?.message === "string" && e.message) ? e.message : fallback;
}
