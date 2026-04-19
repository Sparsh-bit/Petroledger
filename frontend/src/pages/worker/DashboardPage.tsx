import { FormEvent, useEffect, useState } from "react";
import { Banknote, Gauge, History } from "lucide-react";
import toast from "react-hot-toast";
import { Button, Input } from "../../components/ui";
import { Skeleton } from "../../components/ui/Skeleton";
import { api } from "../../api/client";
import { shiftsApi } from "../../api/shifts";

interface Shift {
  id: string;
  pump_id: string;
  worker_id: string;
  start_time: string;
  end_time: string | null;
  status: string;
}

interface NozzleAssignment {
  assignment_id: string;
  shift_id: string;
  nozzle_id: string;
  nozzle_number: number;
  fuel_type: string;
  product_name: string | null;
  assigned_at: string;
}

interface Reading {
  id: string;
  nozzle_id: string;
  closing_reading: number | string | null;
  created_at: string;
}

async function safeGet<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await api.get<T>(path);
    return res.data;
  } catch {
    return fallback;
  }
}

function extractErr(err: unknown, fallback: string): string {
  const e = err as {
    response?: { data?: { message?: string; detail?: string } };
    message?: string;
  };
  return (
    e?.response?.data?.detail ||
    e?.response?.data?.message ||
    e?.message ||
    fallback
  );
}

export default function WorkerDashboardPage() {
  const [currentShift, setCurrentShift] = useState<Shift | null>(null);
  const [assignments, setAssignments] = useState<NozzleAssignment[]>([]);
  const [recentReadings, setRecentReadings] = useState<Reading[]>([]);
  const [loading, setLoading] = useState(true);
  const [nozzle, setNozzle] = useState("");
  const [reading, setReading] = useState("");
  const [amount, setAmount] = useState("");

  async function loadAll() {
    setLoading(true);
    try {
      const s = await shiftsApi.list({ status: "ACTIVE", page: 1, page_size: 1 });
      const active = s.items[0] ?? null;
      setCurrentShift(active);
      const a = await safeGet<NozzleAssignment[]>(
        "/nozzle-assignments/my-active",
        [],
      );
      setAssignments(a);
      if (a.length > 0) setNozzle((prev) => prev || a[0].nozzle_id);

      if (active) {
        const readings = await shiftsApi.getMeterReadings(active.id);
        const list = Array.isArray(readings)
          ? readings
          : readings.items ?? [];
        setRecentReadings(list.slice(0, 5) as Reading[]);
      } else {
        setRecentReadings([]);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  async function submitReading(e: FormEvent) {
    e.preventDefault();
    if (!currentShift) {
      toast.error("No active shift.");
      return;
    }
    if (!nozzle) {
      toast.error("Pick a nozzle.");
      return;
    }
    try {
      await shiftsApi.saveMeterReadings(currentShift.id, {
        nozzle_id: nozzle,
        closing_reading: Number(reading),
      });
      toast.success("Reading submitted.");
      setReading("");
      void loadAll();
    } catch (err) {
      toast.error(extractErr(err, "Submit failed."));
    }
  }

  async function submitCash(e: FormEvent) {
    e.preventDefault();
    if (!currentShift) {
      toast.error("No active shift.");
      return;
    }
    try {
      await shiftsApi.saveCashEntry({
        shift_id: currentShift.id,
        physical_cash: Number(amount),
      });
      toast.success("Cash entry submitted.");
      setAmount("");
    } catch (err) {
      toast.error(extractErr(err, "Submit failed."));
    }
  }

  const noNozzles = !loading && assignments.length === 0;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Worker Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Log your meter readings and shift activity.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-wider text-slate-500">
              Current shift
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-900">
              {loading ? (
                <Skeleton className="h-7 w-40" />
              ) : currentShift ? (
                currentShift.id.slice(0, 8)
              ) : (
                "None active"
              )}
            </div>
            {currentShift && (
              <div className="text-xs text-slate-500 mt-1">
                Started {new Date(currentShift.start_time).toLocaleString()}
              </div>
            )}
          </div>
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              currentShift
                ? "bg-emerald-100 text-emerald-700"
                : "bg-slate-100 text-slate-500"
            }`}
          >
            {currentShift ? "ACTIVE" : "NO SHIFT"}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-4 text-slate-900">
            <Gauge className="h-4 w-4 text-amber-500" /> Submit meter reading
          </h3>

          {noNozzles ? (
            <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              No nozzles assigned — contact your manager.
            </div>
          ) : (
            <form onSubmit={submitReading} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-medium uppercase tracking-wide text-slate-500">
                  Nozzle
                </label>
                <select
                  value={nozzle}
                  onChange={(e) => setNozzle(e.target.value)}
                  disabled={!currentShift}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none focus:border-amber-500"
                >
                  {assignments.map((a) => (
                    <option key={a.nozzle_id} value={a.nozzle_id}>
                      #{a.nozzle_number} — {a.product_name ?? a.fuel_type}
                    </option>
                  ))}
                </select>
              </div>
              <Input
                label="Closing reading"
                name="reading"
                type="number"
                step="0.01"
                required
                placeholder="0.00"
                value={reading}
                onChange={(e) => setReading(e.target.value)}
                disabled={!currentShift}
              />
              <Button type="submit" disabled={!currentShift} className="w-full">
                Submit reading
              </Button>
            </form>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-4 text-slate-900">
            <Banknote className="h-4 w-4 text-amber-500" /> Submit cash entry
          </h3>
          <form onSubmit={submitCash} className="space-y-4">
            <Input
              label="Amount (₹)"
              name="amount"
              type="number"
              step="0.01"
              required
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              disabled={!currentShift}
            />
            <Button
              type="submit"
              variant="secondary"
              disabled={!currentShift}
              className="w-full"
            >
              Submit cash
            </Button>
          </form>
        </div>
      </div>

      <section>
        <h2 className="text-base font-semibold text-slate-900 mb-3 flex items-center gap-2">
          <History className="h-4 w-4 text-slate-500" />
          Last 5 readings
        </h2>
        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
          {recentReadings.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-500">
              No readings yet — submit your first one above.
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {recentReadings.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between px-5 py-3 text-sm"
                >
                  <div className="font-mono text-xs text-slate-600">
                    {r.nozzle_id.slice(0, 8)}
                  </div>
                  <div className="text-slate-700">
                    closing: {String(r.closing_reading ?? "—")}
                  </div>
                  <div className="text-xs text-slate-500">
                    {new Date(r.created_at).toLocaleTimeString()}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
