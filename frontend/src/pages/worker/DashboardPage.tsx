import { FormEvent, useEffect, useState } from "react";
import { Banknote, Gauge } from "lucide-react";
import toast from "react-hot-toast";
import { Button, Card, Input, Badge } from "../../components/ui";
import { Spinner } from "../../components/ui/Spinner";
import { api } from "../../api/client";

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

function extractErr(err: unknown, fallback: string): string {
  return (
    (err as { response?: { data?: { message?: string } } })?.response?.data
      ?.message || fallback
  );
}

export default function WorkerDashboardPage() {
  const [currentShift, setCurrentShift] = useState<Shift | null>(null);
  const [assignments, setAssignments] = useState<NozzleAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [nozzle, setNozzle] = useState("");
  const [reading, setReading] = useState("");
  const [amount, setAmount] = useState("");

  useEffect(() => {
    void (async () => {
      setLoading(true);
      const s = await safeGet<Paged<Shift>>(
        "/shifts/?status=ACTIVE&page=1&page_size=1",
        { items: [], total: 0 },
      );
      setCurrentShift(s.items[0] ?? null);
      const a = await safeGet<NozzleAssignment[]>(
        "/nozzle-assignments/my-active",
        [],
      );
      setAssignments(a);
      if (a.length > 0) setNozzle(a[0].nozzle_id);
      setLoading(false);
    })();
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
      await api.post(`/meter-readings/shifts/${currentShift.id}/manual`, {
        nozzle_id: nozzle,
        closing_reading: Number(reading),
      });
      toast.success("Reading submitted.");
      setReading("");
    } catch (err: unknown) {
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
      await api.post(`/cash-entries/`, {
        shift_id: currentShift.id,
        physical_cash: Number(amount),
      });
      toast.success("Cash entry submitted.");
      setAmount("");
    } catch (err: unknown) {
      toast.error(extractErr(err, "Submit failed."));
    }
  }

  const noNozzles = !loading && assignments.length === 0;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Worker Dashboard</h1>
        <p className="mt-1 text-ink-400 text-sm">
          Log your meter readings and shift activity.
        </p>
      </div>

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-wider text-ink-500">
              Current shift
            </div>
            <div className="mt-2 text-2xl font-bold">
              {loading ? (
                <Spinner size={18} />
              ) : currentShift ? (
                currentShift.id.slice(0, 8)
              ) : (
                "None active"
              )}
            </div>
            {currentShift && (
              <div className="text-xs text-ink-400 mt-1">
                Started {new Date(currentShift.start_time).toLocaleString()}
              </div>
            )}
          </div>
          <Badge tone={currentShift ? "green" : "slate"}>
            {currentShift ? "ACTIVE" : "NO SHIFT"}
          </Badge>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
            <Gauge className="h-4 w-4 text-brand-300" /> Submit meter reading
          </h3>

          {noNozzles ? (
            <div className="text-sm text-amber-300">
              No nozzles assigned — contact your manager.
            </div>
          ) : (
            <form onSubmit={submitReading} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-medium uppercase tracking-wide text-ink-400">
                  Nozzle
                </label>
                <select
                  value={nozzle}
                  onChange={(e) => setNozzle(e.target.value)}
                  disabled={!currentShift}
                  className="w-full rounded-lg border border-ink-700 bg-ink-900/60 px-3.5 py-2.5 text-sm text-ink-50 outline-none focus:border-brand-400"
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
        </Card>

        <Card>
          <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
            <Banknote className="h-4 w-4 text-amber-300" /> Submit cash entry
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
        </Card>
      </div>
    </div>
  );
}
