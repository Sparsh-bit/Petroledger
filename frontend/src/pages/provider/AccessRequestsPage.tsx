import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { Card } from "../../components/ui";
import {
  AccessRequest,
  AccessRequestStatus,
  accessRequestsApi,
} from "../../api/access-requests";

const STATUS_FILTERS: { label: string; value: AccessRequestStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "New", value: "NEW" },
  { label: "Contacted", value: "CONTACTED" },
  { label: "Approved", value: "APPROVED" },
  { label: "Rejected", value: "REJECTED" },
];

const STATUS_BADGE: Record<AccessRequestStatus, string> = {
  NEW: "bg-amber-400/15 text-amber-300 ring-1 ring-amber-400/30",
  CONTACTED: "bg-sky-400/15 text-sky-300 ring-1 ring-sky-400/30",
  APPROVED: "bg-emerald-400/15 text-emerald-300 ring-1 ring-emerald-400/30",
  REJECTED: "bg-red-400/15 text-red-300 ring-1 ring-red-400/30",
};

function relativeTime(iso: string): string {
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function AccessRequestsPage() {
  const [items, setItems] = useState<AccessRequest[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<AccessRequestStatus | "">("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    accessRequestsApi
      .list({
        status: statusFilter || undefined,
        search: search.trim() || undefined,
        page,
        page_size: pageSize,
      })
      .then((res) => {
        if (cancel) return;
        setItems(res.items);
        setTotal(res.total);
        setError(null);
      })
      .catch((e) => !cancel && setError(e?.message ?? "Failed to load"))
      .finally(() => !cancel && setLoading(false));
    return () => {
      cancel = true;
    };
  }, [statusFilter, search, page, pageSize]);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total, pageSize],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Access Requests</h1>
        <p className="mt-1 text-ink-400 text-sm">
          Public ERP access requests submitted from the marketing site.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 rounded-lg border border-ink-800 bg-ink-900/50 p-1">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.label}
              type="button"
              onClick={() => {
                setStatusFilter(f.value);
                setPage(1);
              }}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
                statusFilter === f.value
                  ? "bg-amber-400 text-slate-950"
                  : "text-ink-300 hover:text-white hover:bg-ink-800"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-500" />
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search name, email, company…"
            className="w-full rounded-lg border border-ink-800 bg-ink-900/60 pl-9 pr-3 py-2 text-sm text-ink-50 placeholder:text-ink-500 outline-none focus:border-amber-400/60"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      <Card className="p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ink-900/80 text-xs uppercase text-ink-400">
            <tr>
              <th className="text-left px-4 py-3">Submitted</th>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Company</th>
              <th className="text-left px-4 py-3">Email</th>
              <th className="text-left px-4 py-3">Phone</th>
              <th className="text-left px-4 py-3">Pumps</th>
              <th className="text-left px-4 py-3">Location</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && items.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-ink-500">
                  Loading…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-ink-500">
                  No requests match your filters.
                </td>
              </tr>
            ) : (
              items.map((r) => (
                <tr
                  key={r.id}
                  className="border-t border-ink-800 hover:bg-ink-900/40 transition"
                >
                  <td className="px-4 py-3 text-ink-400 text-xs">
                    <Link to={`/provider/access-requests/${r.id}`}>
                      {relativeTime(r.created_at)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-medium">
                    <Link
                      to={`/provider/access-requests/${r.id}`}
                      className="hover:text-amber-300"
                    >
                      {r.full_name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-ink-300">{r.company}</td>
                  <td className="px-4 py-3 text-ink-300">{r.email}</td>
                  <td className="px-4 py-3 text-ink-300 font-mono text-xs">
                    {r.phone}
                  </td>
                  <td className="px-4 py-3 text-ink-300">
                    {r.pump_count_range}
                  </td>
                  <td className="px-4 py-3 text-ink-300 text-xs">
                    {r.city}, {r.state}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider ${
                        STATUS_BADGE[r.status as AccessRequestStatus]
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>

      <div className="flex items-center justify-between text-xs text-ink-400">
        <div>
          {total} total · page {page} of {totalPages}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="px-3 py-1.5 rounded-md border border-ink-800 disabled:opacity-40 hover:bg-ink-800"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="px-3 py-1.5 rounded-md border border-ink-800 disabled:opacity-40 hover:bg-ink-800"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
