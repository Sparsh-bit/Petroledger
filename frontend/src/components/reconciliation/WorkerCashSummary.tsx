import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Banknote, Play, Users } from "lucide-react";
import { Badge, Button, Card } from "../ui";
import { Spinner } from "../ui/Spinner";
import {
  adminApi,
  PerWorkerResult,
  PerWorkerReconciliationResponse,
} from "../../api/admin";
import { errMsg } from "../../lib/errMsg";

function toNum(v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0;
  return Number(v) || 0;
}

function formatINR(n: number): string {
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function statusTone(status: string): "green" | "red" | "amber" {
  if (status === "MATCH") return "green";
  if (status === "SHORTAGE") return "red";
  return "amber";
}

function varianceColor(variance: number): string {
  if (variance > 0) return "text-red-600 font-semibold";
  if (variance < 0) return "text-amber-600 font-semibold";
  return "text-emerald-600 font-semibold";
}

export interface WorkerCashSummaryProps {
  shiftId: string;
  /** If true, show the "Run Per-Worker Recon" button. */
  canRun?: boolean;
  /** Callback after a successful run, to refresh parent data. */
  onReconciled?: () => void;
}

export function WorkerCashSummary({
  shiftId,
  canRun = false,
  onReconciled,
}: WorkerCashSummaryProps) {
  const [data, setData] = useState<PerWorkerReconciliationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [hasRun, setHasRun] = useState(false);

  async function fetchResults() {
    setLoading(true);
    try {
      const res = await adminApi.getPerWorkerReconciliation(shiftId);
      setData(res);
      setHasRun(true);
    } catch {
      // No results yet — that's fine
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  async function runReconciliation() {
    setRunning(true);
    try {
      const res = await adminApi.runPerWorkerReconciliation(shiftId);
      setData(res);
      setHasRun(true);
      toast.success("Per-worker reconciliation complete.");
      onReconciled?.();
    } catch (err) {
      toast.error(errMsg(err, "Per-worker reconciliation failed."));
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    void fetchResults();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shiftId]);

  if (loading) {
    return (
      <Card>
        <Spinner label="Loading worker breakdown…" />
      </Card>
    );
  }

  if (!data || data.results.length === 0) {
    return (
      <Card>
        <div className="flex flex-col items-center gap-3 py-8 text-center">
          <Users className="h-8 w-8 text-slate-400" />
          <div>
            <h4 className="font-semibold text-slate-900">
              No per-worker breakdown available
            </h4>
            <p className="text-sm text-slate-500 mt-1">
              {hasRun
                ? "No meter readings found for this shift. Upload opening and closing receipts first."
                : "Run per-worker reconciliation to see how much cash to collect from each worker."}
            </p>
          </div>
          {canRun && (
            <Button onClick={runReconciliation} disabled={running}>
              <Play className="h-4 w-4" />
              {running ? "Running…" : "Run Per-Worker Reconciliation"}
            </Button>
          )}
        </div>
      </Card>
    );
  }

  const results = data.results;
  const totalVariance = toNum(data.total_variance);
  const totalSale = toNum(data.total_shift_sale);

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <SummaryCard
          icon={Banknote}
          label="Total Shift Sale"
          value={`₹${formatINR(totalSale)}`}
          tone="text-emerald-600 bg-emerald-50"
        />
        <SummaryCard
          icon={Users}
          label="Workers"
          value={String(results.length)}
          tone="text-sky-600 bg-sky-50"
        />
        <SummaryCard
          icon={Banknote}
          label="Total Variance"
          value={`₹${formatINR(Math.abs(totalVariance))}`}
          subtitle={
            totalVariance > 0
              ? "Shortage"
              : totalVariance < 0
                ? "Excess"
                : "Balanced"
          }
          tone={
            totalVariance > 0
              ? "text-red-600 bg-red-50"
              : totalVariance < 0
                ? "text-amber-600 bg-amber-50"
                : "text-emerald-600 bg-emerald-50"
          }
        />
      </div>

      {/* Worker breakdown table */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-slate-900 flex items-center gap-2">
            <Users className="h-4 w-4 text-slate-500" />
            Cash to Collect per Worker
          </h3>
          {canRun && (
            <Button
              variant="secondary"
              onClick={runReconciliation}
              disabled={running}
            >
              {running ? "Running…" : "Re-run"}
            </Button>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="text-left px-4 py-2.5">Worker</th>
                <th className="text-left px-4 py-2.5">Nozzle</th>
                <th className="text-right px-4 py-2.5">Shift Sale</th>
                <th className="text-right px-4 py-2.5">UPI</th>
                <th className="text-right px-4 py-2.5">Card/POS</th>
                <th className="text-right px-4 py-2.5">Fleet</th>
                <th className="text-right px-4 py-2.5 font-bold">
                  Expected Cash
                </th>
                <th className="text-right px-4 py-2.5">Actual Cash</th>
                <th className="text-right px-4 py-2.5">Variance</th>
                <th className="text-center px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {results.map((r) => (
                <WorkerRow key={`${r.nozzle_id}-${r.worker_id}`} result={r} />
              ))}
            </tbody>
            <tfoot className="bg-slate-50 font-semibold text-sm">
              <tr>
                <td className="px-4 py-2.5 text-slate-900" colSpan={2}>
                  Total
                </td>
                <td className="px-4 py-2.5 text-right text-slate-900">
                  ₹{formatINR(totalSale)}
                </td>
                <td className="px-4 py-2.5 text-right text-slate-600">
                  ₹{formatINR(results.reduce((a, r) => a + toNum(r.upi_received), 0))}
                </td>
                <td className="px-4 py-2.5 text-right text-slate-600">
                  ₹{formatINR(results.reduce((a, r) => a + toNum(r.card_settled), 0))}
                </td>
                <td className="px-4 py-2.5 text-right text-slate-600">
                  ₹{formatINR(results.reduce((a, r) => a + toNum(r.fleet_card), 0))}
                </td>
                <td className="px-4 py-2.5 text-right text-slate-900">
                  ₹{formatINR(results.reduce((a, r) => a + toNum(r.expected_cash), 0))}
                </td>
                <td className="px-4 py-2.5 text-right text-slate-900">
                  ₹{formatINR(results.reduce((a, r) => a + toNum(r.actual_cash), 0))}
                </td>
                <td
                  className={`px-4 py-2.5 text-right ${varianceColor(totalVariance)}`}
                >
                  ₹{formatINR(Math.abs(totalVariance))}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────────────────── */

function WorkerRow({ result: r }: { result: PerWorkerResult }) {
  const variance = toNum(r.variance);
  return (
    <tr
      className={`hover:bg-slate-50 ${
        r.status === "SHORTAGE"
          ? "bg-red-50/40"
          : r.status === "EXCESS"
            ? "bg-amber-50/40"
            : ""
      }`}
    >
      <td className="px-4 py-2.5 font-medium text-slate-900">
        {r.worker_name}
      </td>
      <td className="px-4 py-2.5 text-slate-600">#{r.nozzle_number}</td>
      <td className="px-4 py-2.5 text-right text-slate-700">
        ₹{formatINR(toNum(r.shift_sale_amount))}
      </td>
      <td className="px-4 py-2.5 text-right text-slate-600">
        ₹{formatINR(toNum(r.upi_received))}
      </td>
      <td className="px-4 py-2.5 text-right text-slate-600">
        ₹{formatINR(toNum(r.card_settled))}
      </td>
      <td className="px-4 py-2.5 text-right text-slate-600">
        ₹{formatINR(toNum(r.fleet_card))}
      </td>
      <td className="px-4 py-2.5 text-right font-bold text-slate-900">
        ₹{formatINR(toNum(r.expected_cash))}
      </td>
      <td className="px-4 py-2.5 text-right text-slate-700">
        ₹{formatINR(toNum(r.actual_cash))}
      </td>
      <td className={`px-4 py-2.5 text-right ${varianceColor(variance)}`}>
        {variance > 0 ? "-" : variance < 0 ? "+" : ""}₹
        {formatINR(Math.abs(variance))}
      </td>
      <td className="px-4 py-2.5 text-center">
        <Badge tone={statusTone(r.status)}>{r.status}</Badge>
      </td>
    </tr>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value,
  subtitle,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  subtitle?: string;
  tone: string;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-500">
            {label}
          </div>
          <div className="mt-2 text-2xl font-bold text-slate-900">{value}</div>
          {subtitle && (
            <div className="mt-0.5 text-xs text-slate-500">{subtitle}</div>
          )}
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
