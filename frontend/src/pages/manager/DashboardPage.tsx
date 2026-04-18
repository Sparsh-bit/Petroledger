import { FormEvent, useEffect, useState } from "react";
import { Activity, Banknote, ClipboardList, Play, Plus } from "lucide-react";
import toast from "react-hot-toast";
import { Button, Card, Badge, Input } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { api } from "../../api/client";

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
  amount?: string | number;
  physical_cash?: string | number;
  entry_type?: string;
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

function errMsg(err: unknown, fallback: string): string {
  return (
    (err as { response?: { data?: { message?: string } } })?.response?.data
      ?.message || fallback
  );
}

export default function ManagerDashboardPage() {
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [cash, setCash] = useState<CashEntry[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [pumps, setPumps] = useState<Pump[]>([]);
  const [nozzles, setNozzles] = useState<Nozzle[]>([]);

  const [startOpen, setStartOpen] = useState(false);
  const [cashOpen, setCashOpen] = useState(false);
  const [readingOpen, setReadingOpen] = useState(false);

  async function refresh() {
    const s = await safeGet<Paged<Shift>>(
      "/shifts/?page=1&page_size=10",
      { items: [], total: 0 },
    );
    setShifts(s.items);
    const c = await safeGet<Paged<CashEntry> | CashEntry[]>(
      "/cash-entries/?page=1&page_size=10",
      { items: [], total: 0 },
    );
    const list = Array.isArray(c) ? c : (c as Paged<CashEntry>).items ?? [];
    setCash(list.slice(0, 10));
  }

  useEffect(() => {
    void refresh();
    void (async () => {
      const w = await safeGet<Paged<Worker> | Worker[]>(
        "/workers/?page=1&page_size=100",
        [],
      );
      setWorkers(Array.isArray(w) ? w : w.items ?? []);
      const p = await safeGet<Paged<Pump> | Pump[]>(
        "/pumps/?page=1&page_size=100",
        [],
      );
      setPumps(Array.isArray(p) ? p : p.items ?? []);
    })();
  }, []);

  // When a pump is picked inside the Start Shift modal we may want its nozzles;
  // they live under the pump record (nozzles relationship). Load them lazily.
  async function loadNozzlesForPump(pumpId: string) {
    const res = await safeGet<Pump & { nozzles?: Nozzle[] }>(
      `/pumps/${pumpId}`,
      { id: pumpId, name: "", nozzles: [] } as unknown as Pump & {
        nozzles?: Nozzle[];
      },
    );
    setNozzles(res.nozzles ?? []);
  }

  const activeShifts = shifts.filter((s) => s.status === "ACTIVE").length;
  const cashTotal = cash.reduce(
    (sum, c) => sum + Number(c.physical_cash ?? c.amount ?? 0),
    0,
  );

  const kpis = [
    {
      label: "Active shifts",
      value: activeShifts,
      icon: Activity,
      tone: "text-sky-300",
    },
    {
      label: "Cash entries",
      value: cash.length,
      icon: ClipboardList,
      tone: "text-brand-300",
    },
    {
      label: "Cash total (₹)",
      value: cashTotal.toLocaleString("en-IN"),
      icon: Banknote,
      tone: "text-amber-300",
    },
  ] as const;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Manager Dashboard</h1>
        <p className="mt-1 text-ink-400 text-sm">
          Approve shifts, review variance, manage staff.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
        <h2 className="text-lg font-semibold mb-3">Quick actions</h2>
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
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">Recent shifts</h2>
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ink-900/80 text-xs uppercase text-ink-400">
              <tr>
                <th className="text-left px-5 py-3">Shift</th>
                <th className="text-left px-5 py-3">Worker</th>
                <th className="text-left px-5 py-3">Started</th>
                <th className="text-left px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {shifts.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-5 py-6 text-center text-ink-500"
                  >
                    No data yet.
                  </td>
                </tr>
              )}
              {shifts.map((s) => (
                <tr key={s.id} className="border-t border-ink-800">
                  <td className="px-5 py-3 font-mono text-xs">
                    {s.id.slice(0, 8)}
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-ink-400">
                    {s.worker_id.slice(0, 8)}
                  </td>
                  <td className="px-5 py-3 text-ink-300">
                    {new Date(s.start_time).toLocaleString()}
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
        shifts={shifts.filter((s) => s.status === "ACTIVE")}
        onCreated={() => {
          setCashOpen(false);
          void refresh();
        }}
      />
      <SubmitReadingModal
        open={readingOpen}
        onClose={() => setReadingOpen(false)}
        shifts={shifts.filter((s) => s.status === "ACTIVE")}
        nozzles={nozzles}
        onLoadNozzles={loadNozzlesForPump}
        pumps={pumps}
        onSubmitted={() => {
          setReadingOpen(false);
        }}
      />
    </div>
  );
}

// ── Start Shift ───────────────────────────────────────────────────────────

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
      await api.post("/shifts/", {
        pump_id: pumpId,
        worker_id: workerId,
        start_time: new Date().toISOString(),
      });
      toast.success("Shift started.");
      onCreated();
    } catch (err: unknown) {
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
          <Button onClick={(e) => void onSubmit(e as unknown as FormEvent)} disabled={busy || !pumpId || !workerId}>
            {busy ? "Starting…" : "Start"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="block text-xs uppercase tracking-wide text-ink-400">
            Pump
          </label>
          <select
            value={pumpId}
            onChange={(e) => setPumpId(e.target.value)}
            className="w-full rounded-lg border border-ink-700 bg-ink-900/60 px-3.5 py-2.5 text-sm"
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
          <label className="block text-xs uppercase tracking-wide text-ink-400">
            Worker
          </label>
          <select
            value={workerId}
            onChange={(e) => setWorkerId(e.target.value)}
            className="w-full rounded-lg border border-ink-700 bg-ink-900/60 px-3.5 py-2.5 text-sm"
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

// ── Cash Entry ────────────────────────────────────────────────────────────

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
      await api.post("/cash-entries/", {
        shift_id: shiftId,
        physical_cash: Number(amount),
      });
      toast.success("Cash entry recorded.");
      onCreated();
    } catch (err: unknown) {
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
          <label className="block text-xs uppercase tracking-wide text-ink-400">
            Active shift
          </label>
          <select
            value={shiftId}
            onChange={(e) => setShiftId(e.target.value)}
            className="w-full rounded-lg border border-ink-700 bg-ink-900/60 px-3.5 py-2.5 text-sm"
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

// ── Submit reading ────────────────────────────────────────────────────────

function SubmitReadingModal({
  open,
  onClose,
  shifts,
  nozzles,
  pumps,
  onLoadNozzles,
  onSubmitted,
}: {
  open: boolean;
  onClose: () => void;
  shifts: Shift[];
  nozzles: Nozzle[];
  pumps: Pump[];
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
    } catch (err: unknown) {
      toast.error(errMsg(err, "Failed to submit reading."));
    } finally {
      setBusy(false);
    }
  }

  // placate unused var warning
  void pumps;

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
          <label className="block text-xs uppercase tracking-wide text-ink-400">
            Active shift
          </label>
          <select
            value={shiftId}
            onChange={(e) => setShiftId(e.target.value)}
            className="w-full rounded-lg border border-ink-700 bg-ink-900/60 px-3.5 py-2.5 text-sm"
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
          <label className="block text-xs uppercase tracking-wide text-ink-400">
            Nozzle
          </label>
          <select
            value={nozzleId}
            onChange={(e) => setNozzleId(e.target.value)}
            className="w-full rounded-lg border border-ink-700 bg-ink-900/60 px-3.5 py-2.5 text-sm"
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
