import { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Banknote, Clock, Gauge } from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { PageHeader } from "../../components/ui/PageHeader";
import { SkeletonCard } from "../../components/ui/Skeleton";
import { adminApi, Nozzle } from "../../api/admin";
import { shiftsApi, MeterReading, CashEntry } from "../../api/shifts";
import { errMsg } from "../../lib/errMsg";

interface ActiveShift {
  id: string;
  pump_id: string;
  worker_id: string;
  start_time: string;
  status: string;
}


function unwrap<T>(res: T[] | { items: T[] }): T[] {
  return Array.isArray(res) ? res : res.items ?? [];
}

export default function MyShiftPage() {
  const [shift, setShift] = useState<ActiveShift | null>(null);
  const [nozzles, setNozzles] = useState<Nozzle[]>([]);
  const [readings, setReadings] = useState<MeterReading[]>([]);
  const [cash, setCash] = useState<CashEntry[]>([]);
  const [closings, setClosings] = useState<Record<string, string>>({});
  const [cashAmount, setCashAmount] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await shiftsApi.list({
        status: "ACTIVE",
        page: 1,
        page_size: 1,
      });
      const active = (res.items[0] as ActiveShift | undefined) ?? null;
      setShift(active);
      if (active) {
        const pump = await adminApi.getPump(active.pump_id).catch(() => null);
        setNozzles(pump?.nozzles ?? []);
        const [r, c] = await Promise.all([
          shiftsApi.getMeterReadings(active.id).catch(() => []),
          shiftsApi.getCashEntries({ shift_id: active.id }).catch(() => []),
        ]);
        setReadings(unwrap(r as MeterReading[] | { items: MeterReading[] }));
        setCash(unwrap(c as CashEntry[] | { items: CashEntry[] }));
      } else {
        setNozzles([]);
        setReadings([]);
        setCash([]);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function submitReadings(e: FormEvent) {
    e.preventDefault();
    if (!shift) return;
    const entries = Object.entries(closings).filter(
      ([, v]) => v && v.trim() !== "",
    );
    if (entries.length === 0) {
      toast.error("Enter at least one reading.");
      return;
    }
    setBusy(true);
    try {
      for (const [nozzleId, val] of entries) {
        await shiftsApi.saveMeterReadings(shift.id, {
          nozzle_id: nozzleId,
          closing_reading: Number(val),
        });
      }
      toast.success("Readings submitted.");
      setClosings({});
      void load();
    } catch (err) {
      toast.error(errMsg(err, "Submit failed."));
    } finally {
      setBusy(false);
    }
  }

  async function submitCash(e: FormEvent) {
    e.preventDefault();
    if (!shift) return;
    if (!cashAmount.trim()) {
      toast.error("Enter a cash amount.");
      return;
    }
    setBusy(true);
    try {
      await shiftsApi.saveCashEntry({
        shift_id: shift.id,
        physical_cash: Number(cashAmount),
      });
      toast.success("Cash entry submitted.");
      setCashAmount("");
      void load();
    } catch (err) {
      toast.error(errMsg(err, "Submit failed."));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard lines={3} />
        <SkeletonCard lines={5} />
      </div>
    );
  }

  if (!shift) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="My shift"
          description="Meter readings and cash entries for your active shift."
        />
        <Card>
          <div className="flex flex-col items-center gap-2 py-10 text-slate-500">
            <Clock className="h-6 w-6 text-slate-400" />
            <span className="text-sm">
              No active shift. Contact your manager to start one.
            </span>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="My shift"
        description="Submit meter readings and cash during the shift."
        actions={<Badge tone="green">{shift.status}</Badge>}
      />

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-500">
              Shift
            </div>
            <div className="mt-1 text-2xl font-bold text-slate-900 font-mono">
              {shift.id.slice(0, 8)}
            </div>
            <div className="text-xs text-slate-500 mt-1">
              Started {new Date(shift.start_time).toLocaleString()}
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Gauge className="h-4 w-4 text-amber-500" /> Meter readings
          </h3>
          {nozzles.length === 0 ? (
            <p className="text-sm text-slate-500">
              No nozzles configured on this pump.
            </p>
          ) : (
            <form onSubmit={submitReadings} className="space-y-3">
              {nozzles.map((n) => {
                const existing = readings.find((r) => r.nozzle_id === n.id);
                const opening = existing?.opening_reading;
                return (
                  <div key={n.id} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-700">
                        Nozzle #{n.nozzle_number} — {n.fuel_type}
                      </span>
                      <span className="text-slate-500">
                        Opening: {opening !== null && opening !== undefined ? String(opening) : "—"}
                      </span>
                    </div>
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="Closing reading"
                      value={closings[n.id] ?? ""}
                      onChange={(e) =>
                        setClosings((prev) => ({
                          ...prev,
                          [n.id]: e.target.value,
                        }))
                      }
                    />
                  </div>
                );
              })}
              <Button type="submit" disabled={busy} className="w-full">
                {busy ? "Submitting…" : "Submit readings"}
              </Button>
            </form>
          )}
        </Card>

        <Card>
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Banknote className="h-4 w-4 text-amber-500" /> Cash entry
          </h3>
          <form onSubmit={submitCash} className="space-y-4">
            <Input
              label="Cash counted (₹)"
              type="number"
              min={0}
              step="0.01"
              required
              value={cashAmount}
              onChange={(e) => setCashAmount(e.target.value)}
            />
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? "Submitting…" : "Submit cash"}
            </Button>
          </form>
          {cash.length > 0 && (
            <div className="mt-6">
              <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">
                Recent entries
              </div>
              <ul className="divide-y divide-slate-100 text-sm">
                {cash.slice(0, 5).map((c) => (
                  <li
                    key={c.id}
                    className="py-2 flex items-center justify-between"
                  >
                    <span className="text-slate-500 font-mono text-xs">
                      {new Date(c.created_at).toLocaleTimeString()}
                    </span>
                    <span className="font-medium text-slate-900">
                      ₹
                      {Number(c.physical_cash ?? c.amount ?? 0).toLocaleString(
                        "en-IN",
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
