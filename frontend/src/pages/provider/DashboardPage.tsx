import { Link } from "react-router-dom";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Inbox,
  Lock,
  TrendingUp,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Card } from "../../components/ui";
import { PageHeader } from "../../components/ui/PageHeader";
import { SkeletonCard, SkeletonList } from "../../components/ui/Skeleton";
import {
  providerApi,
  TenantSummary,
} from "../../api/provider";
import { accessRequestsApi, AccessRequest } from "../../api/access-requests";

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export default function ProviderDashboardPage() {
  const kpisQ = useQuery({
    queryKey: ["provider-kpis"],
    queryFn: () => providerApi.getProviderKpis(),
    placeholderData: (prev) => prev,
  });

  const tenantsQ = useQuery({
    queryKey: ["tenants"],
    queryFn: () => providerApi.getTenants(),
    placeholderData: (prev) => prev,
  });

  const requestsQ = useQuery({
    queryKey: ["access-requests-new"],
    queryFn: () => accessRequestsApi.list({ status: "NEW", page_size: 5 }),
    placeholderData: (prev) => prev,
  });

  const loading = kpisQ.isPending;
  const stats = kpisQ.data ?? null;
  const recent: TenantSummary[] = (Array.isArray(tenantsQ.data) ? tenantsQ.data : []).slice(0, 6);
  const newRequests: AccessRequest[] = requestsQ.data?.items ?? [];
  const newRequestCount = requestsQ.data?.total ?? 0;

  const cards = [
    {
      label: "Total tenants",
      value: stats ? String(stats.total_orgs) : "—",
      icon: Building2,
      tone: "text-sky-600 bg-sky-50",
    },
    {
      label: "Active",
      value: stats ? String(stats.active_orgs) : "—",
      icon: CheckCircle2,
      tone: "text-emerald-600 bg-emerald-50",
    },
    {
      label: "Locked",
      value: stats ? String(stats.locked_orgs) : "—",
      icon: Lock,
      tone: "text-red-600 bg-red-50",
    },
    {
      label: "MRR",
      value: stats ? `₹${stats.mrr_inr.toLocaleString("en-IN")}` : "—",
      icon: TrendingUp,
      tone: "text-indigo-600 bg-indigo-50",
    },
    {
      label: "New requests",
      value: String(newRequestCount),
      icon: Inbox,
      tone: "text-amber-600 bg-amber-50",
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Provider dashboard"
        description="Platform-wide health across every tenant."
      />

      {kpisQ.error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          Could not load KPIs. Check your connection and reload.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <Card key={c.label}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs uppercase tracking-wider text-slate-500">
                    {c.label}
                  </div>
                  <div className="mt-2 text-2xl font-bold text-slate-900">
                    {loading ? <div className="h-7 w-16 rounded bg-slate-200 animate-pulse" /> : c.value}
                  </div>
                </div>
                <span
                  className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ${c.tone}`}
                >
                  <Icon className="h-5 w-5" />
                </span>
              </div>
            </Card>
          );
        })}
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-slate-900">
            Recent access requests
          </h2>
          <Link
            to="/provider/access-requests"
            className="text-sm text-indigo-600 hover:text-indigo-500 inline-flex items-center gap-1"
          >
            View all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          {requestsQ.isPending ? (
            <div className="p-4"><SkeletonList rows={3} /></div>
          ) : newRequests.length === 0 ? (
            <div className="px-5 py-6 text-center text-slate-500 text-sm">
              No new access requests.
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {newRequests.map((r) => (
                <li key={r.id}>
                  <Link
                    to={`/provider/access-requests/${r.id}`}
                    className="flex items-center justify-between px-5 py-3 hover:bg-slate-50"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-slate-900 truncate">
                        {r.full_name}
                      </div>
                      <div className="text-xs text-slate-500 truncate">
                        {r.company} · {r.city}, {r.state}
                      </div>
                    </div>
                    <div className="text-xs text-slate-400 ml-3 shrink-0">
                      {relativeTime(r.created_at)}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div>
        <h2 className="text-base font-semibold text-slate-900 mb-3">
          Recent signups
        </h2>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="text-left px-5 py-3">Name</th>
                <th className="text-left px-5 py-3">Plan</th>
                <th className="text-left px-5 py-3">Orgs</th>
                <th className="text-left px-5 py-3">Users</th>
                <th className="text-left px-5 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {recent.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-5 py-6 text-center text-slate-500"
                  >
                    No tenants yet.
                  </td>
                </tr>
              )}
              {recent.map((o) => (
                <tr key={o.tenant_id} className="hover:bg-slate-50">
                  <td className="px-5 py-3 font-medium text-slate-900">
                    <Link
                      to={`/provider/tenants/${o.tenant_id}`}
                      className="hover:text-indigo-600"
                    >
                      {o.name}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-slate-600">
                    {o.subscription_plan}
                  </td>
                  <td className="px-5 py-3 text-slate-600">{o.org_count}</td>
                  <td className="px-5 py-3 text-slate-600">{o.user_count}</td>
                  <td className="px-5 py-3 text-slate-500">
                    {new Date(o.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
