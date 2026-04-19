import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  BarChart3,
  Banknote,
  Fuel,
  AlertTriangle,
  TrendingUp,
} from "lucide-react";
import { Card } from "../../components/ui";
import { Select } from "../../components/ui/Select";
import { PageHeader } from "../../components/ui/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import {
  adminApi,
  CashflowRow,
  GradeSalesRow,
  VarianceTrendRow,
} from "../../api/admin";
import { useOrgStore } from "../../store/org";

interface AnalyticsData {
  variance: VarianceTrendRow[];
  grades: GradeSalesRow[];
  cashflow: CashflowRow[];
}

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function AnalyticsPage() {
  const { selectedOrgId } = useOrgStore();
  const [days, setDays] = useState(7);
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!selectedOrgId) return;
    let cancel = false;
    (async () => {
      setLoading(true);
      try {
        const d = await adminApi.getAnalytics({ org_id: selectedOrgId, days });
        if (!cancel) setData(d);
      } catch (err) {
        if (!cancel) toast.error(errMsg(err, "Failed to load analytics."));
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [selectedOrgId, days]);

  const totals = useMemo(() => {
    if (!data) {
      return { revenue: 0, litres: 0, varianceAbs: 0, anomalies: 0 };
    }
    const revenue = data.grades.reduce((a, r) => a + Number(r.amount || 0), 0);
    const litres = data.grades.reduce((a, r) => a + Number(r.volume || 0), 0);
    const varianceAbs = data.variance.reduce(
      (a, r) => a + Math.abs(Number(r.total_variance || 0)),
      0,
    );
    const anomalies = data.variance.reduce(
      (a, r) => a + (r.shortage_count ?? 0) + (r.excess_count ?? 0),
      0,
    );
    return { revenue, litres, varianceAbs, anomalies };
  }, [data]);

  if (!selectedOrgId) {
    return (
      <div className="space-y-6">
        <PageHeader title="Analytics" />
        <Card>
          <p className="text-sm text-slate-600">
            Pick an organisation in the top bar to load analytics.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description="Revenue, variance, and anomaly trends across this organisation."
        actions={
          <div className="w-40">
            <Select
              value={String(days)}
              onChange={(e) => setDays(Number(e.target.value))}
              options={[
                { value: "7", label: "Last 7 days" },
                { value: "30", label: "Last 30 days" },
                { value: "90", label: "Last 90 days" },
              ]}
            />
          </div>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi
          icon={Banknote}
          label="Revenue"
          value={`₹${totals.revenue.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
          tone="text-emerald-600 bg-emerald-50"
          loading={loading}
        />
        <Kpi
          icon={Fuel}
          label="Litres sold"
          value={totals.litres.toLocaleString("en-IN", {
            maximumFractionDigits: 0,
          })}
          tone="text-sky-600 bg-sky-50"
          loading={loading}
        />
        <Kpi
          icon={TrendingUp}
          label="Abs variance"
          value={`₹${totals.varianceAbs.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
          tone="text-indigo-600 bg-indigo-50"
          loading={loading}
        />
        <Kpi
          icon={AlertTriangle}
          label="Anomalies"
          value={String(totals.anomalies)}
          tone="text-amber-600 bg-amber-50"
          loading={loading}
        />
      </div>

      <Card>
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="h-4 w-4 text-slate-500" />
          <h3 className="font-semibold text-slate-900">Variance by day</h3>
        </div>
        {loading ? (
          <Spinner label="Loading…" />
        ) : (
          <VarianceChart rows={data?.variance ?? []} />
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h3 className="font-semibold text-slate-900 mb-4">
            Revenue by fuel grade
          </h3>
          {loading ? (
            <Spinner label="Loading…" />
          ) : (
            <FuelGradeTable rows={data?.grades ?? []} />
          )}
        </Card>
        <Card>
          <h3 className="font-semibold text-slate-900 mb-4">Daily cashflow</h3>
          {loading ? (
            <Spinner label="Loading…" />
          ) : (
            <CashflowTable rows={data?.cashflow ?? []} />
          )}
        </Card>
      </div>
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone,
  loading,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone: string;
  loading: boolean;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500">
            {label}
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">
            {loading ? "…" : value}
          </div>
        </div>
        <span
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ${tone}`}
        >
          <Icon className="h-5 w-5" />
        </span>
      </div>
    </Card>
  );
}

function VarianceChart({ rows }: { rows: VarianceTrendRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No variance data in selected window.
      </p>
    );
  }
  const values = rows.map((r) => Number(r.total_variance || 0));
  const max = Math.max(...values.map(Math.abs), 1);
  const width = Math.max(rows.length * 40, 320);
  const height = 160;
  const pad = 20;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  const points = values
    .map((v, i) => {
      const x = pad + (i / Math.max(values.length - 1, 1)) * plotW;
      const y = pad + plotH / 2 - (v / max) * (plotH / 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="overflow-x-auto">
      <svg width={width} height={height} className="text-indigo-500">
        <line
          x1={pad}
          x2={width - pad}
          y1={pad + plotH / 2}
          y2={pad + plotH / 2}
          stroke="#e2e8f0"
        />
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          points={points}
        />
        {values.map((v, i) => {
          const x = pad + (i / Math.max(values.length - 1, 1)) * plotW;
          const y = pad + plotH / 2 - (v / max) * (plotH / 2);
          return <circle key={i} cx={x} cy={y} r={3} fill="currentColor" />;
        })}
      </svg>
      <div className="mt-2 flex justify-between text-[10px] text-slate-500">
        <span>{rows[0]?.date}</span>
        <span>{rows[rows.length - 1]?.date}</span>
      </div>
    </div>
  );
}

function FuelGradeTable({ rows }: { rows: GradeSalesRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No fuel-grade data.</p>;
  }
  // Aggregate by fuel_type
  const map = new Map<string, { volume: number; amount: number }>();
  for (const r of rows) {
    const curr = map.get(r.fuel_type) ?? { volume: 0, amount: 0 };
    curr.volume += Number(r.volume || 0);
    curr.amount += Number(r.amount || 0);
    map.set(r.fuel_type, curr);
  }
  const list = Array.from(map.entries());
  return (
    <table className="w-full text-sm">
      <thead className="text-xs uppercase text-slate-500">
        <tr>
          <th className="text-left py-2">Fuel</th>
          <th className="text-right py-2">Volume (L)</th>
          <th className="text-right py-2">Revenue</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {list.map(([fuel, v]) => (
          <tr key={fuel}>
            <td className="py-2 font-medium text-slate-900">{fuel}</td>
            <td className="py-2 text-right">
              {v.volume.toLocaleString("en-IN", { maximumFractionDigits: 1 })}
            </td>
            <td className="py-2 text-right">
              ₹{v.amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CashflowTable({ rows }: { rows: CashflowRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No cashflow data.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs uppercase text-slate-500">
          <tr>
            <th className="text-left py-2">Day</th>
            <th className="text-right py-2">Cash</th>
            <th className="text-right py-2">UPI</th>
            <th className="text-right py-2">Card</th>
            <th className="text-right py-2">Fleet</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={r.date}>
              <td className="py-2 text-slate-700">{r.date}</td>
              <td className="py-2 text-right">
                ₹{Number(r.cash).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              </td>
              <td className="py-2 text-right">
                ₹{Number(r.upi).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              </td>
              <td className="py-2 text-right">
                ₹{Number(r.card).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              </td>
              <td className="py-2 text-right">
                ₹{Number(r.fleet).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
