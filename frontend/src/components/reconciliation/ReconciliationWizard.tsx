import { FormEvent, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { ArrowLeft, ArrowRight, CheckCircle2, Play, RefreshCw } from "lucide-react";
import { Badge, Button, Card, Input } from "../ui";
import { DataTable } from "../ui/DataTable";
import { Spinner } from "../ui/Spinner";
import { adminApi, ReconciliationResult, Shift } from "../../api/admin";
import { shiftsApi } from "../../api/shifts";
import { errMsg } from "../../lib/errMsg";
import { WorkerCashSummary } from "./WorkerCashSummary";

type Step = 1 | 2 | 3;


function toNum(v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0;
  return Number(v) || 0;
}

export interface ReconciliationWizardProps {
  /** Optional org-scope filter. */
  orgId?: string | null;
}

export function ReconciliationWizard({ orgId }: ReconciliationWizardProps) {
  const [step, setStep] = useState<Step>(1);
  const [queue, setQueue] = useState<Shift[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Shift | null>(null);
  const [posTotal, setPosTotal] = useState(0);
  const [cashTotal, setCashTotal] = useState(0);
  const [upiTotal, setUpiTotal] = useState(0);
  const [actualCash, setActualCash] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ReconciliationResult | null>(null);

  async function loadQueue() {
    setLoading(true);
    try {
      const res = await adminApi.getReconciliationQueue({
        org_id: orgId ?? undefined,
        page: 1,
        page_size: 50,
      });
      setQueue(res?.items ?? []);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load queue."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadQueue();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  async function gotoReview(shift: Shift) {
    setSelected(shift);
    setResult(null);
    setStep(2);
    try {
      const [p, c, u] = await Promise.all([
        shiftsApi.getPosTransactions({ shift_id: shift.id }).catch(() => []),
        shiftsApi.getCashEntries({ shift_id: shift.id }).catch(() => []),
        shiftsApi.getUpiTransactions({ shift_id: shift.id }).catch(() => []),
      ]);
      const posArr = Array.isArray(p) ? p : p.items ?? [];
      const cashArr = Array.isArray(c) ? c : c.items ?? [];
      const upiArr = Array.isArray(u) ? u : u.items ?? [];
      setPosTotal(posArr.reduce((acc, t) => acc + toNum(t.amount), 0));
      setCashTotal(
        cashArr.reduce((acc, t) => acc + toNum(t.physical_cash ?? t.amount), 0),
      );
      setUpiTotal(upiArr.reduce((acc, t) => acc + toNum(t.amount), 0));
    } catch {
      /* totals are best-effort */
    }
  }

  async function run(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    const amt = Number(actualCash);
    if (Number.isNaN(amt) || amt < 0) {
      toast.error("Enter a valid cash amount.");
      return;
    }
    setRunning(true);
    try {
      const r = await adminApi.runReconciliation(selected.id, amt);
      setResult(r);
      setStep(3);
      toast.success("Reconciliation complete.");
    } catch (err) {
      toast.error(errMsg(err, "Reconciliation failed."));
    } finally {
      setRunning(false);
    }
  }

  const stepper = useMemo(
    () => (
      <ol className="flex items-center gap-2 text-xs">
        {[
          [1, "Select shift"],
          [2, "Review data"],
          [3, "Result"],
        ].map(([n, label]) => {
          const done = step > (n as number);
          const active = step === n;
          return (
            <li key={n as number} className="flex items-center gap-2">
              <span
                className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold ${
                  active
                    ? "bg-indigo-600 text-white"
                    : done
                      ? "bg-emerald-600 text-white"
                      : "bg-slate-200 text-slate-500"
                }`}
              >
                {n}
              </span>
              <span
                className={`${
                  active ? "text-slate-900 font-medium" : "text-slate-500"
                }`}
              >
                {label}
              </span>
              {n !== 3 && <span className="text-slate-300">›</span>}
            </li>
          );
        })}
      </ol>
    ),
    [step],
  );

  return (
    <div className="space-y-6">
      {stepper}

      {step === 1 && (
        <>
          {loading ? (
            <Card>
              <Spinner label="Loading queue…" />
            </Card>
          ) : (
            <DataTable<Shift>
              data={queue}
              rowKey={(s) => s.id}
              onRowClick={(s) => void gotoReview(s)}
              emptyState="No completed shifts pending reconciliation."
              columns={[
                {
                  key: "id",
                  header: "Shift",
                  render: (s) => (
                    <span className="font-mono text-xs">
                      {s.id.slice(0, 8)}
                    </span>
                  ),
                },
                {
                  key: "started",
                  header: "Started",
                  render: (s) => new Date(s.start_time).toLocaleString(),
                },
                {
                  key: "ended",
                  header: "Ended",
                  render: (s) =>
                    s.end_time ? new Date(s.end_time).toLocaleString() : "—",
                },
                {
                  key: "status",
                  header: "Status",
                  render: (s) => <Badge tone="amber">{s.status}</Badge>,
                },
                {
                  key: "cta",
                  header: "",
                  align: "right",
                  render: () => (
                    <span className="text-xs text-indigo-600 inline-flex items-center gap-1">
                      Review <ArrowRight className="h-3 w-3" />
                    </span>
                  ),
                },
              ]}
            />
          )}
        </>
      )}

      {step === 2 && selected && (
        <Card>
          <h3 className="font-semibold text-slate-900 mb-4">
            Review shift totals
          </h3>
          <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
            <Stat label="POS total" value={`₹${posTotal.toLocaleString("en-IN")}`} />
            <Stat label="UPI total" value={`₹${upiTotal.toLocaleString("en-IN")}`} />
            <Stat label="Cash recorded" value={`₹${cashTotal.toLocaleString("en-IN")}`} />
          </dl>
          <form onSubmit={run} className="mt-6 flex items-end gap-3 flex-wrap">
            <div className="flex-1 max-w-xs">
              <Input
                label="Actual cash counted (₹)"
                type="number"
                min={0}
                step="0.01"
                value={actualCash}
                onChange={(e) => setActualCash(e.target.value)}
                required
              />
            </div>
            <Button variant="ghost" type="button" onClick={() => setStep(1)}>
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
            <Button type="submit" disabled={running || !actualCash}>
              <Play className="h-4 w-4" />
              {running ? "Running…" : "Run reconciliation"}
            </Button>
          </form>
        </Card>
      )}

      {step === 3 && result && (
        <>
        <Card>
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            <h3 className="font-semibold text-slate-900">
              Reconciliation complete
            </h3>
          </div>
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <Stat label="Status" value={result.status} />
            <Stat
              label="Expected"
              value={`₹${toNum(result.expected_cash).toLocaleString("en-IN")}`}
            />
            <Stat
              label="Actual"
              value={`₹${toNum(result.actual_cash).toLocaleString("en-IN")}`}
            />
            <Stat
              label="Variance"
              value={`₹${toNum(result.variance).toLocaleString("en-IN")}`}
              tone={toNum(result.variance) > 0 ? "text-red-600" : toNum(result.variance) < 0 ? "text-amber-600" : "text-emerald-600"}
            />
          </dl>

          {result.confidence_score != null && (
            <div className="mt-4 flex items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-slate-500">Confidence</span>
              <div className="flex-1 max-w-xs bg-slate-100 rounded-full h-2">
                <div
                  className="bg-emerald-500 h-2 rounded-full transition-all"
                  style={{ width: `${Math.min(100, toNum(result.confidence_score) * 100)}%` }}
                />
              </div>
              <span className="text-sm font-medium text-slate-700">
                {(toNum(result.confidence_score) * 100).toFixed(1)}%
              </span>
            </div>
          )}

          {result.narration_summary && (
            <div className="mt-4 rounded-lg bg-indigo-50 border border-indigo-200 px-4 py-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-indigo-700 mb-1">
                AI Summary
              </h4>
              <p className="text-sm text-indigo-900 leading-relaxed">
                {result.narration_summary}
              </p>
            </div>
          )}

          {result.variance_reason && (
            <div className="mt-4 rounded-lg bg-slate-50 border border-slate-200 px-4 py-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
                Variance Reason
              </h4>
              <p className="text-sm font-medium text-slate-800">
                {result.variance_reason.replace(/_/g, " ")}
              </p>
              {result.variance_notes && (
                <p className="text-sm text-slate-600 mt-1">{result.variance_notes}</p>
              )}
            </div>
          )}

          {result.anomalies && result.anomalies.length > 0 && (
            <div className="mt-6">
              <h4 className="text-sm font-semibold text-slate-900 mb-2">
                Anomaly flags
              </h4>
              <ul className="space-y-2 text-sm">
                {result.anomalies.map((a: Record<string, unknown>, i: number) => {
                  const severity = String(a.severity ?? "low").toUpperCase();
                  const isHigh = severity === "HIGH" || severity === "CRITICAL";
                  const isMedium = severity === "MEDIUM";
                  return (
                    <li
                      key={i}
                      className={`rounded-md border px-3 py-2 flex items-start justify-between gap-2 ${
                        isHigh
                          ? "bg-red-50 border-red-200"
                          : isMedium
                            ? "bg-amber-50 border-amber-200"
                            : "bg-slate-50 border-slate-200"
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="font-medium text-slate-900">
                          {String(a.flag_type ?? a.type ?? "Anomaly").replace(/_/g, " ")}
                        </div>
                        {a.description != null && (
                          <div className="text-slate-600 mt-0.5 text-xs">
                            {String(a.description)}
                          </div>
                        )}
                        {a.amount != null && (
                          <div className="text-slate-500 font-mono text-xs mt-0.5">
                            ₹{toNum(a.amount as string | number).toLocaleString("en-IN")}
                          </div>
                        )}
                      </div>
                      <Badge
                        tone={isHigh ? "red" : isMedium ? "amber" : "slate"}
                      >
                        {severity}
                      </Badge>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {result.grade_breakdown && Object.keys(result.grade_breakdown).length > 0 && (
            <div className="mt-6">
              <h4 className="text-sm font-semibold text-slate-900 mb-2">
                Fuel Grade Breakdown
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="text-left px-3 py-2">Grade</th>
                      <th className="text-right px-3 py-2">Volume (L)</th>
                      <th className="text-right px-3 py-2">Amount (₹)</th>
                      <th className="text-right px-3 py-2">Unit Price</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {Object.entries(result.grade_breakdown as Record<string, Record<string, string>>).map(
                      ([code, data]) => (
                        <tr key={code}>
                          <td className="px-3 py-2 font-medium text-slate-900">{code}</td>
                          <td className="px-3 py-2 text-right text-slate-700">
                            {toNum(data.volume_litres).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                          </td>
                          <td className="px-3 py-2 text-right text-slate-700">
                            ₹{toNum(data.amount).toLocaleString("en-IN")}
                          </td>
                          <td className="px-3 py-2 text-right text-slate-500">
                            ₹{toNum(data.unit_price).toFixed(2)}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="mt-6 flex gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setStep(1);
                setSelected(null);
                setResult(null);
                setActualCash("");
                void loadQueue();
              }}
            >
              <RefreshCw className="h-4 w-4" /> Back to queue
            </Button>
          </div>
        </Card>

        {/* Per-Worker breakdown after reconciliation */}
        {selected && (
          <div className="mt-4">
            <WorkerCashSummary shiftId={selected.id} canRun />
          </div>
        )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className={`mt-1 text-lg font-semibold ${tone ?? "text-slate-900"}`}>{value}</dd>
    </div>
  );
}
