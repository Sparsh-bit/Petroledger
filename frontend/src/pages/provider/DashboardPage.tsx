import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Building2,
  CheckCircle2,
  Inbox,
  Lock,
  TrendingUp,
  ArrowRight,
} from "lucide-react";
import { Card } from "../../components/ui";
import { providerApi, ProviderStats, OrganizationSummary } from "../../api/provider";
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
  const [stats, setStats] = useState<ProviderStats | null>(null);
  const [recent, setRecent] = useState<OrganizationSummary[]>([]);
  const [newRequests, setNewRequests] = useState<AccessRequest[]>([]);
  const [newRequestCount, setNewRequestCount] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([providerApi.stats(), providerApi.organizations()])
      .then(([s, o]) => {
        setStats(s);
        setRecent(o.slice(0, 6));
      })
      .catch((e) => setError(e?.message ?? "Failed to load"));
    accessRequestsApi
      .list({ status: "NEW", page_size: 5 })
      .then((r) => {
        setNewRequests(r.items);
        setNewRequestCount(r.total);
      })
      .catch(() => {
        /* non-blocking */
      });
  }, []);

  const cards = [
    {
      label: "Total Orgs",
      value: stats?.total_orgs ?? "—",
      icon: Building2,
      tone: "text-sky-300",
    },
    {
      label: "Active",
      value: stats?.active_orgs ?? "—",
      icon: CheckCircle2,
      tone: "text-brand-300",
    },
    {
      label: "Locked",
      value: stats?.locked_orgs ?? "—",
      icon: Lock,
      tone: "text-red-300",
    },
    {
      label: "MRR (₹)",
      value: stats ? stats.mrr_inr.toLocaleString("en-IN") : "—",
      icon: TrendingUp,
      tone: "text-amber-300",
    },
    {
      label: "New requests",
      value: newRequestCount,
      icon: Inbox,
      tone: "text-amber-300",
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Provider Dashboard</h1>
        <p className="mt-1 text-ink-400 text-sm">
          Platform-wide health across every tenant.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {cards.map((c) => (
          <Card key={c.label} className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-wider text-ink-500">
                {c.label}
              </div>
              <div className="mt-2 text-3xl font-bold">{c.value}</div>
            </div>
            <c.icon className={`h-6 w-6 ${c.tone}`} />
          </Card>
        ))}
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Recent access requests</h2>
          <Link
            to="/provider/access-requests"
            className="text-sm text-amber-300 hover:text-amber-200 inline-flex items-center gap-1"
          >
            View all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
        <Card className="p-0 overflow-hidden">
          {newRequests.length === 0 ? (
            <div className="px-5 py-6 text-center text-ink-500 text-sm">
              No new access requests.
            </div>
          ) : (
            <ul className="divide-y divide-ink-800">
              {newRequests.map((r) => (
                <li key={r.id}>
                  <Link
                    to={`/provider/access-requests/${r.id}`}
                    className="flex items-center justify-between px-5 py-3 hover:bg-ink-900/40"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">
                        {r.full_name}
                      </div>
                      <div className="text-xs text-ink-400 truncate">
                        {r.company} · {r.city}, {r.state}
                      </div>
                    </div>
                    <div className="text-xs text-ink-500 ml-3 shrink-0">
                      {relativeTime(r.created_at)}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">Recent signups</h2>
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ink-900/80 text-xs uppercase text-ink-400">
              <tr>
                <th className="text-left px-5 py-3">Name</th>
                <th className="text-left px-5 py-3">Plan</th>
                <th className="text-left px-5 py-3">Pumps</th>
                <th className="text-left px-5 py-3">Users</th>
                <th className="text-left px-5 py-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {recent.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-6 text-center text-ink-500">
                    No organisations yet.
                  </td>
                </tr>
              )}
              {recent.map((o) => (
                <tr key={o.tenant_id} className="border-t border-ink-800">
                  <td className="px-5 py-3 font-medium">{o.name}</td>
                  <td className="px-5 py-3 text-ink-300">
                    {o.subscription_plan}
                  </td>
                  <td className="px-5 py-3 text-ink-300">{o.pump_count}</td>
                  <td className="px-5 py-3 text-ink-300">{o.user_count}</td>
                  <td className="px-5 py-3 text-ink-400">
                    {new Date(o.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
