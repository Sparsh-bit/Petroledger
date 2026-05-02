import { FormEvent, useEffect, useState } from "react";
import {
  Activity,
  Banknote,
  ClipboardList,
  Play,
  Plus,
  RefreshCw,
} from "lucide-react";
import toast from "react-hot-toast";
import { Button, Input } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { Skeleton, SkeletonList } from "../../components/ui/Skeleton";
import { shiftsApi } from "../../api/shifts";
import { adminApi } from "../../api/admin";
import { api } from "../../api/client";
import { errMsg } from "../../lib/errMsg";

interface Shift {
  id: string;
  pump_id: string;
  worker_id: string;
  start_time: string;
  end_time: string | null;
  status: string;
}

interface Worker {
  id: string;
  employee_code: string;
  pump_id: string;
}

interface Nozzle {
  id: string;
  nozzle_number: number;
  fuel_type: string;
}

interface Pump {
  id: string;
  name: string;
}

interface CashEntry {
  id: string;
  physical_cash?: string | number;
  amount?: string | number;
  created_at: string;
}



function statusTone(status: string): string {
  const s = status.toUpperCase();
  if (s === "ACTIVE") return "bg-blue-100 text-blue-700";
  if (s === "COMPLETED" || s === "RECONCILED") return "bg-slate-100 text-slate-700";
  return "bg-slate-100 text-slate-500";
}

export default function ManagerDashboardPage() {
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [cash, setCash] = useState<CashEntry[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [pumps, setPumps] = useState<Pump[]>([]);
  const [nozzles, setNozzles] = useState<Nozzle[]>([]);
  const [loading, setLoading] = useState(true);

  const [startOpen, setStartOpen] = useState(false);
  const [cashOpen, setCashOpen] = useState(false);
  const [readingOpen, setReadingOpen] = useState(false);

  async function refresh() {
    try {
      const [s, c] = await Promise.all([
        shiftsApi.list({ page: 1, page_size: 10 }),
        shiftsApi.getCashEntries({ page: 1 }),
      ]);
      setShifts(Array.isArray(s) ? s : s?.items ?? []);
      const list = Array.isArray(c) ? c : c?.items ?? [];
      setCash(list.slice(0, 10));
    } catch (err) {
      toast.error(errMsg(err, "Failed to load dashboard."));
    }
  }

  useEffect(() => {
    void (async () => {
      setLoading(true);
      try {
        await refresh();
        const [w, p] = await Promise.all([
          adminApi.getWorkers({ page: 1, page_size: 100 }).catch(() => []),
          adminApi.getPumps({ page: 1, page_size: 100 }).catch(() => []),
        ]);
        setWorkers(Array.isArray(w) ? (w as Worker[]) : ((w as { items: Worker[] }).items ?? []));
        setPumps(Array.isArray(p) ? (p as Pump[]) : ((p as { items: Pump[] }).items ?? []));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function loadNozzlesForPump(pumpId: string) {
    try {
      const res = await adminApi.getPump(pumpId);
      setNozzles(res.nozzles ?? []);
    } catch {
      setNozzles([]);
    }
  }

  const activeShifts = shifts.filter((s) => s.status === "ACTIVE");
  const pendingRecon = shifts.filter((s) => s.status === "COMPLETED").length;
  const cashTotal = cash.reduce(
    (sum, c) => sum + Number(c.physical_cash ?? c.amount ?? 0),
    0,
  );

  const kpis = [
    {
      label: "Active shifts",
      value: activeShifts.length,
      icon: Activity,
      tone: "text-blue-600 bg-blue-50",
    },
    {
      label: "Pending recon",
      value: pendingRecon,
      icon: RefreshCw,
      tone: "text-indigo-600 bg-indigo-50",
    },
    {
      label: "Cash entries",
      value: cash.length,
      icon: ClipboardList,
      tone: "text-emerald-600 bg-emerald-50",
    },
    {
      label: "Cash total",
      value: `₹${cashTotal.toLocaleString("en-IN")}`,
      icon: Banknote,
      tone: "text-amber-600 bg-amber-50",
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Manager Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Approve shifts, review variance, and run reconciliation.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((k) => {
          const Icon = k.icon;
          return (
            <div
              key={k.label}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs uppercase tracking-wider text-slate-500">
                    {k.label}
                  </div>
                  <div className="mt-2 text-2xl font-bold text-slate-900">
                    {loading ? <Skeleton className="h-7 w-20" /> : k.value}
                  </div>
                </div>
                <span
                  className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ${k.tone}`}
                >
                  <Icon className="h-5 w-5" />
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <section>
        <h2 className="text-base font-semibold text-slate-900 mb-3">
          Quick actions
        </h2>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => setStartOpen(true)}>
            <Play className="h-4 w-4" /> Start shift
          </Button>
          <Button variant="secondary" onClick={() => setReadingOpen(true)}>
            <Plus className="h-4 w-4" /> Submit reading
          </Button>
          <Button variant="secondary" onClick={() => setCashOpen(true)}>
            <Banknote className="h-4 w-4" /> Cash entry
          </Button>
        </div>
      </section>

      <section>
        <h2 className="text-base font-semibold text-slate-900 mb-3">
          Recent shifts
        </h2>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          {loading ? (
            <div className="p-4">
              <SkeletonList rows={5} />
            </div>
          ) : shifts.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">
              No shifts yet — use "Start shift" above to begin.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="text-left px-5 py-3">Shift</th>
                  <th className="text-left px-5 py-3">Worker</th>
                  <th className="text-left px-5 py-3">Started</th>
                  <th className="text-left px-5 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shifts.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3 font-mono text-xs text-slate-700">
                      {s.id.slice(0, 8)}
                    </td>
                    <td className="px-5 py-3 font-mono text-xs text-slate-500">
                      {s.worker_id.slice(0, 8)}
                    </td>
                    <td className="px-5 py-3 text-slate-700">
                      {new Date(s.start_time).toLocaleString()}
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

      <StartShiftModal
        open={startOpen}
        onClose={() => setStartOpen(false)}
        workers={workers}
        pumps={pumps}
        onCreated={() => {
          setStartOpen(false);
          void refresh();
        }}
      />
      <CashEntryModal
        open={cashOpen}
        onClose={() => setCashOpen(false)}
        shifts={activeShifts}
        onCreated={() => {
          setCashOpen(false);
          void refresh();
        }}
      />
      <SubmitReadingModal
        open={readingOpen}
        onClose={() => setReadingOpen(false)}
        shifts={activeShifts}
        nozzles={nozzles}
        onLoadNozzles={loadNozzlesForPump}
        onSubmitted={() => setReadingOpen(false)}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */

function StartShiftModal({
  open,
  onClose,
  workers,
  pumps,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  workers: Worker[];
  pumps: Pump[];
  onCreated: () => void;
}) {
  const [pumpId, setPumpId] = useState("");
  const [workerId, setWorkerId] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await shiftsApi.startShift({
        pump_id: pumpId,
        worker_id: workerId,
        start_time: new Date().toISOString(),
      });
      toast.success("Shift started.");
      onCreated();
    } catch (err) {
      toast.error(errMsg(err, "Failed to start shift."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Start shift"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={busy || !pumpId || !workerId}
          >
            {busy ? "Starting…" : "Start"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-xs uppercase tracking-wide text-slate-500">
            Pump
          </label>
          <select
            value={pumpId}
            onChange={(e) => setPumpId(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900"
          >
            <option value="">Select pump…</option>
            {pumps.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="block text-xs uppercase tracking-wide text-slate-500">
            Worker
          </label>
          <select
            value={workerId}
            onChange={(e) => setWorkerId(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900"
          >
            <option value="">Select worker…</option>
            {workers.map((w) => (
              <option key={w.id} value={w.id}>
                {w.employee_code}
              </option>
            ))}
          </select>
        </div>
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */

function CashEntryModal({
  open,
  onClose,
  shifts,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  shifts: Shift[];
  onCreated: () => void;
}) {
  const [shiftId, setShiftId] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await shiftsApi.saveCashEntry({
        shift_id: shiftId,
        physical_cash: Number(amount),
      });
      toast.success("Cash entry recorded.");
      onCreated();
    } catch (err) {
      toast.error(errMsg(err, "Failed to record cash."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Cash entry"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={busy || !shiftId || !amount}
          >
            {busy ? "Saving…" : "Save"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-xs uppercase tracking-wide text-slate-500">
            Active shift
          </label>
          <select
            value={shiftId}
            onChange={(e) => setShiftId(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900"
          >
            <option value="">Select shift…</option>
            {shifts.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id.slice(0, 8)} — {new Date(s.start_time).toLocaleString()}
              </option>
            ))}
          </select>
        </div>
        <Input
          label="Physical cash (₹)"
          type="number"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */

function SubmitReadingModal({
  open,
  onClose,
  shifts,
  nozzles,
  onLoadNozzles,
  onSubmitted,
}: {
  open: boolean;
  onClose: () => void;
  shifts: Shift[];
  nozzles: Nozzle[];
  onLoadNozzles: (pumpId: string) => Promise<void>;
  onSubmitted: () => void;
}) {
  const [shiftId, setShiftId] = useState("");
  const [nozzleId, setNozzleId] = useState("");
  const [reading, setReading] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!shiftId) return;
    const shift = shifts.find((s) => s.id === shiftId);
    if (shift) void onLoadNozzles(shift.pump_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shiftId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post(`/meter-readings/shifts/${shiftId}/manual`, {
        nozzle_id: nozzleId,
        closing_reading: Number(reading),
      });
      toast.success("Reading submitted.");
      onSubmitted();
    } catch (err) {
      toast.error(errMsg(err, "Failed to submit reading."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Submit meter reading"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={busy || !shiftId || !nozzleId || !reading}
          >
            {busy ? "Submitting…" : "Submit"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-xs uppercase tracking-wide text-slate-500">
            Active shift
          </label>
          <select
            value={shiftId}
            onChange={(e) => setShiftId(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900"
          >
            <option value="">Select shift…</option>
            {shifts.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="block text-xs uppercase tracking-wide text-slate-500">
            Nozzle
          </label>
          <select
            value={nozzleId}
            onChange={(e) => setNozzleId(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900"
          >
            <option value="">Select nozzle…</option>
            {nozzles.map((n) => (
              <option key={n.id} value={n.id}>
                #{n.nozzle_number} — {n.fuel_type}
              </option>
            ))}
          </select>
        </div>
        <Input
          label="Closing reading"
          type="number"
          step="0.01"
          value={reading}
          onChange={(e) => setReading(e.target.value)}
          required
        />
      </form>
    </Modal>
  );
}
