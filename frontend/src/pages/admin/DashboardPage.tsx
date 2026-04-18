import { useEffect, useState } from "react";
import { Activity, Banknote, Flag, Users } from "lucide-react";
import { Card, Badge } from "../../components/ui";
import { Spinner } from "../../components/ui/Spinner";
import { api } from "../../api/client";
import { useOrgStore } from "../../store/org";

interface Shift {
  id: string;
  pump_id: string;
  worker_id: string;
  start_time: string;
  end_time: string | null;
  status: string;
}

interface AnomalyFlag {
  id: string;
  flag_type: string;
  severity: string;
  description?: string | null;
  resolved_at?: string | null;
  created_at: string;
}

interface Paged<T> {
  items: T[];
  total: number;
}

async function safeGet<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await api.get<T>(path);
    return res.data;
  } catch {
    return fallback;
  }
}

export default function AdminDashboardPage() {
  const { selectedOrgId, orgs } = useOrgStore();
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [shiftsTotal, setShiftsTotal] = useState<number | null>(null);
  const [flags, setFlags] = useState<AnomalyFlag[]>([]);
  const [variance, setVariance] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedOrgId) return;
    void (async () => {
      setLoading(true);
      const s = await safeGet<Paged<Shift>>(
        `/shifts/?page=1&page_size=10`,
        { items: [], total: 0 },
      );
      setShifts(s.items);
      setShiftsTotal(s.total);

      const f = await safeGet<Paged<AnomalyFlag>>(
        `/anomaly-flags/?page=1&page_size=5`,
        { items: [], total: 0 },
      );
      setFlags(f.items.filter((x) => !x.resolved_at).slice(0, 5));

      // Analytics variance trend (summed)
      const vt = await safeGet<{ day: string; variance: number }[]>(
        `/analytics/variance-trend?org_id=${selectedOrgId}&days=30`,
        [],
      );
      const total = vt.reduce((acc, d) => acc + Number(d.variance ?? 0), 0);
      setVariance(total);

      setLoading(false);
    })();
  }, [selectedOrgId]);

  const activeShifts = shifts.filter((s) => s.status === "ACTIVE").length;

  const kpis = [
    {
      label: "Variance (30d, ₹)",
      value: variance !== null ? variance.toLocaleString("en-IN") : "—",
      icon: Banknote,
      tone: "text-brand-300",
    },
    {
      label: "Shifts (recent)",
      value: shiftsTotal ?? "—",
      icon: Activity,
      tone: "text-sky-300",
    },
    {
      label: "Active shifts",
      value: activeShifts,
      icon: Users,
      tone: "text-amber-300",
    },
    {
      label: "Unresolved flags",
      value: flags.length,
      icon: Flag,
      tone: "text-red-300",
    },
  ] as const;

  if (orgs.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <Card>
          <div className="text-sm text-ink-400">
            No organizations visible yet. Ask an owner to add you to one.
          </div>
        </Card>
      </div>
    );
  }

  if (!selectedOrgId) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <Card>
          <div className="text-sm text-ink-400">
            Pick an organization in the top bar to see KPIs.
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <p className="mt-1 text-ink-400 text-sm">
          High-level KPIs and organisation health.
        </p>
      </div>

      {loading && <Spinner label="Loading KPIs…" />}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((c) => (
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
        <h2 className="text-lg font-semibold mb-3">Recent shifts</h2>
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ink-900/80 text-xs uppercase text-ink-400">
              <tr>
                <th className="text-left px-5 py-3">Shift</th>
                <th className="text-left px-5 py-3">Started</th>
                <th className="text-left px-5 py-3">Ended</th>
                <th className="text-left px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {shifts.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-6 text-center text-ink-500">
                    No data yet.
                  </td>
                </tr>
              )}
              {shifts.map((s) => (
                <tr key={s.id} className="border-t border-ink-800">
                  <td className="px-5 py-3 font-mono text-xs">
                    {s.id.slice(0, 8)}
                  </td>
                  <td className="px-5 py-3 text-ink-300">
                    {new Date(s.start_time).toLocaleString()}
                  </td>
                  <td className="px-5 py-3 text-ink-400">
                    {s.end_time ? new Date(s.end_time).toLocaleString() : "—"}
                  </td>
                  <td className="px-5 py-3">
                    <Badge tone={s.status === "ACTIVE" ? "green" : "slate"}>
                      {s.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">Anomaly flags</h2>
        <Card>
          {flags.length === 0 ? (
            <div className="text-sm text-ink-500">No unresolved flags.</div>
          ) : (
            <ul className="divide-y divide-ink-800">
              {flags.map((f) => (
                <li
                  key={f.id}
                  className="py-3 flex items-center justify-between"
                >
                  <div>
                    <div className="text-sm font-medium">{f.flag_type}</div>
                    <div className="text-xs text-ink-500">
                      {f.description ?? "—"}
                    </div>
                  </div>
                  <Badge
                    tone={
                      f.severity === "HIGH" || f.severity === "CRITICAL"
                        ? "red"
                        : f.severity === "MEDIUM"
                          ? "amber"
                          : "slate"
                    }
                  >
                    {f.severity}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
