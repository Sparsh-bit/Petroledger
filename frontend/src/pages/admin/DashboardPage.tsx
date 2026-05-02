import {
  Activity,
  AlertTriangle,
  Banknote,
  Fuel,
  RefreshCw,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { adminApi, AnomalyFlag, Pump, Shift } from "../../api/admin";
import { Skeleton, SkeletonList } from "../../components/ui/Skeleton";
import { useOrgStore, useEnsureOrgs, refreshOrgs } from "../../store/org";

interface KpiCard {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  tone: string;
  hint?: string;
}

function formatINR(n: number): string {
  return n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function severityTone(sev: string): string {
  const s = sev.toUpperCase();
  if (s === "HIGH" || s === "CRITICAL") return "bg-red-100 text-red-700";
  if (s === "MEDIUM") return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-700";
}

function statusTone(status: string): string {
  const s = status.toUpperCase();
  if (s === "ACTIVE") return "bg-emerald-100 text-emerald-700";
  if (s === "RECONCILED") return "bg-blue-100 text-blue-700";
  if (s === "COMPLETED") return "bg-slate-100 text-slate-700";
  return "bg-slate-100 text-slate-500";
}

export default function AdminDashboardPage() {
  const { selectedOrgId } = useOrgStore();
  useEnsureOrgs();

  const dashQ = useQuery({
    queryKey: ["admin-dashboard", selectedOrgId],
    queryFn: async () => {
      void refreshOrgs();
      const [shiftsRes, anomaliesRes, varianceRes, pumpsRes] = await Promise.all([
        adminApi.getShifts({ page: 1, page_size: 10, org_id: selectedOrgId ?? undefined }),
        adminApi
          .getAnomalies({ site_id: selectedOrgId ?? undefined, is_resolved: false, page: 1, page_size: 5 })
          .catch(() => ({ items: [] as AnomalyFlag[], total: 0 })),
        selectedOrgId
          ? adminApi.getVarianceTrend(selectedOrgId, 30).catch(() => [])
          : Promise.resolve([]),
        adminApi
          .getPumps({ page: 1, page_size: 10, org_id: selectedOrgId ?? undefined })
          .catch(() => ({ items: [] as Pump[], total: 0 })),
      ]);
      return { shiftsRes, anomaliesRes, varianceRes, pumpsRes };
    },
    placeholderData: (prev) => prev,
  });

  const loading = dashQ.isPending;
  const shifts: Shift[] = dashQ.data?.shiftsRes?.items ?? [];
  const shiftsTotal = dashQ.data?.shiftsRes?.total ?? 0;
  const flags: AnomalyFlag[] = (dashQ.data?.anomaliesRes?.items ?? []).slice(0, 5);
  const pumps: Pump[] = dashQ.data?.pumpsRes?.items ?? [];
  const pumpsTotal = dashQ.data?.pumpsRes?.total ?? 0;
  const variances = Array.isArray(dashQ.data?.varianceRes) ? dashQ.data!.varianceRes : [];
  const varianceTotal = dashQ.data
    ? variances.reduce((acc, r) => acc + Number(r.total_variance ?? 0), 0)
    : null;

  const activeShifts = shifts.filter((s) => s.status === "ACTIVE").length;
  const pendingRecon = shifts.filter(
    (s) => s.status === "COMPLETED" && !s.end_time,
  ).length;

  const kpis: KpiCard[] = [
    {
      label: "Variance (30d)",
      value: varianceTotal !== null ? `₹${formatINR(varianceTotal)}` : "—",
      icon: Banknote,
      tone: "text-emerald-600 bg-emerald-50",
      hint: "Net across all shifts",
    },
    {
      label: "Recent shifts",
      value: shiftsTotal,
      icon: Activity,
      tone: "text-sky-600 bg-sky-50",
    },
    {
      label: "Pumps",
      value: pumpsTotal,
      icon: Fuel,
      tone: "text-purple-600 bg-purple-50",
      hint: "Physical pumps in this org",
    },
    {
      label: "Active shifts",
      value: activeShifts,
      icon: Users,
      tone: "text-amber-600 bg-amber-50",
    },
    {
      label: "Pending recon",
      value: pendingRecon,
      icon: RefreshCw,
      tone: "text-indigo-600 bg-indigo-50",
    },
    {
      label: "Open anomalies",
      value: flags.length,
      icon: AlertTriangle,
      tone: "text-red-600 bg-red-50",
    },
  ];

  return (
    <DashboardShell>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {kpis.map((k) => (
          <KpiCardView key={k.label} card={k} loading={loading} />
        ))}
      </div>

      <section>
        <SectionHeader
          title="Pumps"
          action={<Link to="/admin/pumps" className="text-sm text-emerald-600 hover:text-emerald-500">Manage →</Link>}
        />
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          {loading ? (
            <div className="p-4">
              <SkeletonList rows={3} />
            </div>
          ) : pumps.length === 0 ? (
            <EmptyRow
              icon={Fuel}
              text="No pumps yet — add your first pump from the Pumps page."
            />
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="text-left px-5 py-3">Name</th>
                  <th className="text-left px-5 py-3">Location</th>
                  <th className="text-left px-5 py-3">Nozzles</th>
                  <th className="text-left px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pumps.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3 font-medium text-slate-900">
                      <Link
                        to={`/admin/pumps/${p.id}`}
                        className="hover:text-emerald-600"
                      >
                        {p.name}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {p.location ?? "—"}
                    </td>
                    <td className="px-5 py-3 text-slate-600">
                      {p.nozzle_count ?? 0}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          p.is_active
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {p.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section>
        <SectionHeader
          title="Recent shifts"
          action={<Link to="/admin/shifts" className="text-sm text-emerald-600 hover:text-emerald-500">View all →</Link>}
        />
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          {loading ? (
            <div className="p-4">
              <SkeletonList rows={6} />
            </div>
          ) : shifts.length === 0 ? (
            <EmptyRow
              icon={Fuel}
              text="No shifts yet — start your first shift from the Shifts page."
            />
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="text-left px-5 py-3">Shift</th>
                  <th className="text-left px-5 py-3">Started</th>
                  <th className="text-left px-5 py-3">Ended</th>
                  <th className="text-left px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shifts.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3 font-mono text-xs text-slate-700">
                      {s.id.slice(0, 8)}
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {new Date(s.start_time).toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-slate-500">
                      {s.end_time ? new Date(s.end_time).toLocaleString() : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusTone(s.status)}`}
                      >
                        {s.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <section>
        <SectionHeader
          title="Recent anomalies"
          action={<Link to="/admin/anomalies" className="text-sm text-emerald-600 hover:text-emerald-500">View all →</Link>}
        />
        <div className="rounded-xl border border-slate-200 bg-white">
          {loading ? (
            <div className="p-4">
              <SkeletonList rows={4} />
            </div>
          ) : flags.length === 0 ? (
            <EmptyRow
              icon={AlertTriangle}
              text="No unresolved anomalies. Nice."
            />
          ) : (
            <ul className="divide-y divide-slate-100">
              {flags.map((f) => (
                <li
                  key={f.id}
                  className="flex items-center justify-between px-5 py-3"
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-900 truncate">
                      {f.flag_type}
                    </div>
                    <div className="text-xs text-slate-500 truncate">
                      {f.description}
                    </div>
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${severityTone(f.severity)}`}
                  >
                    {f.severity}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </DashboardShell>
  );
}

/* ------------------------------------------------------------------ */

function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          High-level KPIs and organisation health.
        </p>
      </div>
      {children}
    </div>
  );
}

function KpiCardView({ card, loading }: { card: KpiCard; loading: boolean }) {
  const Icon = card.icon;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wider text-slate-500">
            {card.label}
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {loading ? <Skeleton className="h-7 w-20" /> : card.value}
          </div>
          {card.hint && (
            <div className="mt-1 text-[11px] text-slate-400">{card.hint}</div>
          )}
        </div>
        <span
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ${card.tone}`}
        >
          <Icon className="h-5 w-5" />
        </span>
      </div>
    </div>
  );
}

function SectionHeader({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {action}
    </div>
  );
}

function EmptyRow({
  icon: Icon,
  text,
}: {
  icon: React.ComponentType<{ className?: string }>;
  text: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center text-slate-500">
      <Icon className="h-6 w-6 mb-2 text-slate-400" />
      <p className="text-sm">{text}</p>
    </div>
  );
}

function EmptyOrgState({
  title,
  description,
  cta,
}: {
  title: string;
  description: string;
  cta?: { to: string; label: string };
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center">
      <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
      <p className="mt-2 text-sm text-slate-500">{description}</p>
      {cta && (
        <Link
          to={cta.to}
          className="mt-4 inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
        >
          {cta.label}
        </Link>
      )}
    </div>
  );
}
