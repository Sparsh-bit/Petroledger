import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import {
  ArrowLeft,
  Banknote,
  CreditCard,
  Fuel,
  ReceiptText,
  RefreshCw,
  AlertTriangle,
  Play,
} from "lucide-react";
import { Badge, Button, Card } from "../../components/ui";
import { Input } from "../../components/ui";
import { PageHeader } from "../../components/ui/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { adminApi, Shift, ReconciliationResult, AnomalyFlag } from "../../api/admin";
import {
  shiftsApi,
  MeterReading,
  CashEntry,
  PosTransaction,
  UpiTransaction,
} from "../../api/shifts";
import { statusBadgeTone } from "./ShiftsPage";

type Tab = "overview" | "readings" | "payments" | "reconciliation" | "anomalies";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

function toNum(v: string | number | null | undefined): number {
  if (v === null || v === undefined) return 0;
  return Number(v) || 0;
}

function unwrap<T>(res: T[] | { items: T[] }): T[] {
  return Array.isArray(res) ? res : res.items ?? [];
}

export default function ShiftDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [shift, setShift] = useState<Shift | null>(null);
  const [readings, setReadings] = useState<MeterReading[]>([]);
  const [cash, setCash] = useState<CashEntry[]>([]);
  const [pos, setPos] = useState<PosTransaction[]>([]);
  const [upi, setUpi] = useState<UpiTransaction[]>([]);
  const [recon, setRecon] = useState<ReconciliationResult | null>(null);
  const [anomalies, setAnomalies] = useState<AnomalyFlag[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("overview");

  async function load() {
    if (!id) return;
    setLoading(true);
    try {
      const s = await adminApi.getShift(id);
      setShift(s);
      const [r, c, p, u] = await Promise.all([
        shiftsApi.getMeterReadings(id).catch(() => []),
        shiftsApi.getCashEntries({ shift_id: id }).catch(() => []),
        shiftsApi.getPosTransactions({ shift_id: id }).catch(() => []),
        shiftsApi.getUpiTransactions({ shift_id: id }).catch(() => []),
      ]);
      setReadings(unwrap(r as MeterReading[] | { items: MeterReading[] }));
      setCash(unwrap(c as CashEntry[] | { items: CashEntry[] }));
      setPos(unwrap(p as PosTransaction[] | { items: PosTransaction[] }));
      setUpi(unwrap(u as UpiTransaction[] | { items: UpiTransaction[] }));

      try {
        const rec = await adminApi.getShiftReconciliation(id);
        setRecon(rec);
      } catch {
        setRecon(null);
      }
    } catch (err) {
      toast.error(errMsg(err, "Failed to load shift."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const totals = useMemo(() => {
    const cashTotal = cash.reduce(
      (acc, c) => acc + toNum(c.physical_cash ?? c.amount),
      0,
    );
    const posTotal = pos.reduce((acc, t) => acc + toNum(t.amount), 0);
    const upiTotal = upi.reduce((acc, t) => acc + toNum(t.amount), 0);
    const liters = readings.reduce((acc, r) => {
      const open = toNum(r.opening_reading);
      const close = toNum(r.closing_reading);
      return acc + Math.max(0, close - open);
    }, 0);
    return { cashTotal, posTotal, upiTotal, liters };
  }, [cash, pos, upi, readings]);

  if (loading) {
    return (
      <div className="py-10">
        <Spinner label="Loading shift…" />
      </div>
    );
  }
  if (!shift) {
    return <div className="text-sm text-slate-500">Shift not found.</div>;
  }

  return (
    <div className="space-y-6">
      <Link
        to="/admin/shifts"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" /> All shifts
      </Link>

      <PageHeader
        title={`Shift ${shift.id.slice(0, 8)}`}
        description={`Started ${new Date(shift.start_time).toLocaleString()}`}
        actions={<Badge tone={statusBadgeTone(shift.status)}>{shift.status}</Badge>}
      />

      <Card>
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">
              Pump
            </dt>
            <dd className="mt-1 font-mono text-slate-900">
              {shift.pump_id.slice(0, 8)}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">
              Worker
            </dt>
            <dd className="mt-1 font-mono text-slate-900">
              {shift.worker_id.slice(0, 8)}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">
              Slot
            </dt>
            <dd className="mt-1 text-slate-900">{shift.slot ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">
              Ended
            </dt>
            <dd className="mt-1 text-slate-900">
              {shift.end_time ? new Date(shift.end_time).toLocaleString() : "—"}
            </dd>
          </div>
        </dl>
      </Card>

      <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 w-fit overflow-x-auto">
        {(
          [
            ["overview", "Overview"],
            ["readings", "Meter readings"],
            ["payments", "Payments"],
            ["reconciliation", "Reconciliation"],
            ["anomalies", "Anomalies"],
          ] as const
        ).map(([v, label]) => (
          <button
            key={v}
            type="button"
            onClick={() => setTab(v)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition ${
              tab === v
                ? "bg-indigo-600 text-white"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Kpi
            icon={Fuel}
            label="Litres dispensed"
            value={totals.liters.toLocaleString("en-IN")}
            tone="text-emerald-600 bg-emerald-50"
          />
          <Kpi
            icon={CreditCard}
            label="POS"
            value={`₹${totals.posTotal.toLocaleString("en-IN")}`}
            tone="text-sky-600 bg-sky-50"
          />
          <Kpi
            icon={ReceiptText}
            label="UPI"
            value={`₹${totals.upiTotal.toLocaleString("en-IN")}`}
            tone="text-indigo-600 bg-indigo-50"
          />
          <Kpi
            icon={Banknote}
            label="Cash"
            value={`₹${totals.cashTotal.toLocaleString("en-IN")}`}
            tone="text-amber-600 bg-amber-50"
          />
        </div>
      )}

      {tab === "readings" && (
        <Card>
          <h3 className="font-semibold mb-4 text-slate-900">Meter readings</h3>
          {readings.length === 0 ? (
            <p className="text-sm text-slate-500">
              No readings recorded yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="text-left px-4 py-2">Nozzle</th>
                    <th className="text-right px-4 py-2">Opening</th>
                    <th className="text-right px-4 py-2">Closing</th>
                    <th className="text-right px-4 py-2">Litres</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {readings.map((r) => {
                    const op = toNum(r.opening_reading);
                    const cl = toNum(r.closing_reading);
                    return (
                      <tr key={r.id}>
                        <td className="px-4 py-2 font-mono text-xs text-slate-700">
                          {r.nozzle_id.slice(0, 8)}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {op.toFixed(2)}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {cl.toFixed(2)}
                        </td>
                        <td className="px-4 py-2 text-right font-medium">
                          {Math.max(0, cl - op).toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {tab === "payments" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <PaymentPanel title="POS" icon={CreditCard} items={pos} />
          <PaymentPanel title="UPI" icon={ReceiptText} items={upi} />
          <CashPanel items={cash} />
        </div>
      )}

      {tab === "reconciliation" && (
        <ReconciliationTab
          shift={shift}
          recon={recon}
          onReloaded={load}
        />
      )}

      {tab === "anomalies" && (
        <AnomaliesTab
          anomalies={anomalies}
          setAnomalies={setAnomalies}
          shiftId={shift.id}
        />
      )}
    </div>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
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

function PaymentPanel({
  title,
  icon: Icon,
  items,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  items: Array<{ id: string; amount: string | number; created_at: string }>;
}) {
  const total = items.reduce((acc, t) => acc + toNum(t.amount), 0);
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-900 flex items-center gap-2">
          <Icon className="h-4 w-4 text-slate-500" />
          {title}
        </h3>
        <span className="text-sm font-mono text-slate-700">
          ₹{total.toLocaleString("en-IN")}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">No entries.</p>
      ) : (
        <ul className="divide-y divide-slate-100 max-h-64 overflow-y-auto">
          {items.map((t) => (
            <li key={t.id} className="py-2 text-sm flex justify-between">
              <span className="text-slate-500 font-mono text-xs">
                {new Date(t.created_at).toLocaleTimeString()}
              </span>
              <span className="font-medium text-slate-900">
                ₹{toNum(t.amount).toLocaleString("en-IN")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function CashPanel({ items }: { items: CashEntry[] }) {
  const total = items.reduce(
    (acc, c) => acc + toNum(c.physical_cash ?? c.amount),
    0,
  );
  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-900 flex items-center gap-2">
          <Banknote className="h-4 w-4 text-slate-500" />
          Cash
        </h3>
        <span className="text-sm font-mono text-slate-700">
          ₹{total.toLocaleString("en-IN")}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">No cash entries.</p>
      ) : (
        <ul className="divide-y divide-slate-100 max-h-64 overflow-y-auto">
          {items.map((c) => (
            <li key={c.id} className="py-2 text-sm flex justify-between">
              <span className="text-slate-500 font-mono text-xs">
                {new Date(c.created_at).toLocaleTimeString()}
              </span>
              <span className="font-medium text-slate-900">
                ₹
                {toNum(c.physical_cash ?? c.amount).toLocaleString("en-IN")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ReconciliationTab({
  shift,
  recon,
  onReloaded,
}: {
  shift: Shift;
  recon: ReconciliationResult | null;
  onReloaded: () => void | Promise<void>;
}) {
  const [actualCash, setActualCash] = useState("");
  const [busy, setBusy] = useState(false);

  async function run() {
    const amt = Number(actualCash);
    if (Number.isNaN(amt) || amt < 0) {
      toast.error("Enter a valid cash amount.");
      return;
    }
    setBusy(true);
    try {
      await adminApi.runReconciliation(shift.id, amt);
      toast.success("Reconciliation complete.");
      await onReloaded();
    } catch (err) {
      toast.error(errMsg(err, "Reconciliation failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {recon ? (
        <Card>
          <h3 className="font-semibold mb-4 text-slate-900">Latest result</h3>
          <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <Stat label="Status" value={recon.status} />
            <Stat label="Expected" value={`₹${toNum(recon.expected_cash).toLocaleString("en-IN")}`} />
            <Stat label="Actual" value={`₹${toNum(recon.actual_cash).toLocaleString("en-IN")}`} />
            <Stat
              label="Variance"
              value={`₹${toNum(recon.variance).toLocaleString("en-IN")}`}
            />
          </dl>
        </Card>
      ) : (
        <Card>
          <p className="text-sm text-slate-600">
            Shift not reconciled yet. Enter physical cash counted and run
            reconciliation.
          </p>
        </Card>
      )}

      {shift.status !== "LOCKED" && (
        <Card>
          <h3 className="font-semibold mb-4 text-slate-900 flex items-center gap-2">
            <RefreshCw className="h-4 w-4" /> Run reconciliation
          </h3>
          <div className="flex items-end gap-3">
            <div className="flex-1 max-w-xs">
              <Input
                label="Actual cash (₹)"
                type="number"
                min={0}
                step="0.01"
                value={actualCash}
                onChange={(e) => setActualCash(e.target.value)}
              />
            </div>
            <Button onClick={run} disabled={busy || !actualCash}>
              <Play className="h-4 w-4" />
              {busy ? "Running…" : "Run"}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-lg font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

function AnomaliesTab({
  anomalies,
  setAnomalies,
  shiftId,
}: {
  anomalies: AnomalyFlag[];
  setAnomalies: React.Dispatch<React.SetStateAction<AnomalyFlag[]>>;
  shiftId: string;
}) {
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    // We need the site_id — fetch via shift's pump
    (async () => {
      try {
        const s = await adminApi.getShift(shiftId);
        const pump = await adminApi.getPump(s.pump_id);
        const res = await adminApi.getAnomalies({
          site_id: pump.org_id,
          shift_id: shiftId,
          page_size: 50,
        });
        if (!cancel) setAnomalies(res.items);
      } catch {
        if (!cancel) setAnomalies([]);
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [shiftId, setAnomalies]);

  async function resolve(flag: AnomalyFlag) {
    const note = prompt("Resolution note:");
    if (!note || !note.trim()) return;
    try {
      await adminApi.resolveAnomaly(flag.id, note.trim());
      toast.success("Anomaly resolved.");
      setAnomalies((prev) =>
        prev.map((a) => (a.id === flag.id ? { ...a, is_resolved: true } : a)),
      );
    } catch (err) {
      toast.error(errMsg(err, "Failed to resolve."));
    }
  }

  if (loading) {
    return (
      <div className="py-6">
        <Spinner label="Loading anomalies…" />
      </div>
    );
  }
  if (anomalies.length === 0) {
    return (
      <Card>
        <div className="flex flex-col items-center gap-2 py-6 text-slate-500">
          <AlertTriangle className="h-6 w-6 text-slate-400" />
          <span>No anomalies flagged for this shift.</span>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <ul className="divide-y divide-slate-100">
        {anomalies.map((a) => (
          <li key={a.id} className="py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="font-medium text-slate-900">
                  {a.flag_type}
                </div>
                <div className="text-sm text-slate-600">
                  {a.description}
                </div>
                {a.amount !== null && a.amount !== undefined && (
                  <div className="text-xs text-slate-500 font-mono">
                    Amount: ₹{toNum(a.amount).toLocaleString("en-IN")}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge
                  tone={
                    ["HIGH", "CRITICAL"].includes(a.severity.toUpperCase())
                      ? "red"
                      : a.severity.toUpperCase() === "MEDIUM"
                        ? "amber"
                        : "slate"
                  }
                >
                  {a.severity}
                </Badge>
                {a.is_resolved ? (
                  <Badge tone="green">Resolved</Badge>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={() => void resolve(a)}
                  >
                    Resolve
                  </Button>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
