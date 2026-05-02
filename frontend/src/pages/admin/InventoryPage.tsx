import { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Package, Plus, Droplet } from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { PageHeader } from "../../components/ui/PageHeader";
import { SkeletonCard } from "../../components/ui/Skeleton";
import { adminApi, Tank } from "../../api/admin";
import { useOrgStore, useEnsureOrgs } from "../../store/org";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

function levelTone(pct: number): "green" | "amber" | "red" {
  if (pct >= 50) return "green";
  if (pct >= 20) return "amber";
  return "red";
}

export default function InventoryPage() {
  const { selectedOrgId } = useOrgStore();
  useEnsureOrgs();
  const [tanks, setTanks] = useState<Tank[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [dipTank, setDipTank] = useState<Tank | null>(null);

  async function load() {
    setLoading(true);
    try {
      const res = await adminApi.getTanks({
        org_id: selectedOrgId ?? undefined,
      });
      setTanks(res?.items ?? []);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load tanks."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgId]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inventory"
        description="Fuel tank levels and dip readings."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> Add tank
          </Button>
        }
      />

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <SkeletonCard lines={4} />
          <SkeletonCard lines={4} />
          <SkeletonCard lines={4} />
        </div>
      ) : tanks.length === 0 ? (
        <Card>
          <div className="flex flex-col items-center gap-2 py-8 text-slate-500">
            <Package className="h-6 w-6 text-slate-400" />
            <span>No tanks configured yet.</span>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tanks.map((t) => {
            const cap = Number(t.capacity_litres);
            const cur = Number(t.current_level_litres);
            const pct = cap > 0 ? (cur / cap) * 100 : 0;
            const tone = levelTone(pct);
            const barColor =
              tone === "green"
                ? "bg-emerald-500"
                : tone === "amber"
                  ? "bg-amber-500"
                  : "bg-red-500";
            return (
              <Card key={t.id}>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-wide text-slate-500">
                      Tank #{t.tank_number}
                    </div>
                    <div className="mt-1 text-lg font-bold text-slate-900">
                      {t.fuel_type}
                    </div>
                  </div>
                  <Badge tone={tone}>{pct.toFixed(0)}%</Badge>
                </div>
                <div className="mt-4 space-y-1 text-sm">
                  <div className="flex justify-between text-slate-600">
                    <span>Current</span>
                    <span className="font-mono text-slate-900">
                      {cur.toLocaleString("en-IN")} L
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-500">
                    <span>Capacity</span>
                    <span className="font-mono">
                      {cap.toLocaleString("en-IN")} L
                    </span>
                  </div>
                </div>
                <div className="mt-3 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full ${barColor}`}
                    style={{ width: `${Math.min(100, pct)}%` }}
                  />
                </div>
                <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
                  <span>
                    Last dip:{" "}
                    {t.last_dip_reading_at
                      ? new Date(t.last_dip_reading_at).toLocaleDateString()
                      : "never"}
                  </span>
                  <Button
                    variant="secondary"
                    onClick={() => setDipTank(t)}
                    className="py-1.5 px-3 text-xs"
                  >
                    <Droplet className="h-3 w-3" /> Dip reading
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <CreateTankModal
        open={createOpen}
        orgId={selectedOrgId}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          void load();
        }}
      />
      <DipReadingModal
        tank={dipTank}
        onClose={() => setDipTank(null)}
        onSaved={() => {
          setDipTank(null);
          void load();
        }}
      />
    </div>
  );
}

function CreateTankModal({
  open,
  orgId,
  onClose,
  onCreated,
}: {
  open: boolean;
  orgId: string | null;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [tankNumber, setTankNumber] = useState(1);
  const [fuelType, setFuelType] = useState("PETROL");
  const [capacity, setCapacity] = useState(10000);
  const [threshold, setThreshold] = useState(2000);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!orgId) {
      toast.error("Pick an organisation first.");
      return;
    }
    setBusy(true);
    try {
      await adminApi.createTank({
        org_id: orgId,
        tank_number: tankNumber,
        fuel_type: fuelType,
        capacity_litres: capacity,
        low_level_threshold: threshold,
      });
      toast.success("Tank added.");
      onCreated();
    } catch (err) {
      toast.error(errMsg(err, "Failed to add tank."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add tank"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={busy || capacity <= 0}
          >
            {busy ? "Adding…" : "Add"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="grid grid-cols-2 gap-4">
        <Input
          label="Tank number"
          type="number"
          min={1}
          value={tankNumber}
          onChange={(e) => setTankNumber(Number(e.target.value) || 1)}
          required
        />
        <Select
          label="Fuel type"
          value={fuelType}
          onChange={(e) => setFuelType(e.target.value)}
          options={[
            { value: "PETROL", label: "Petrol" },
            { value: "DIESEL", label: "Diesel" },
            { value: "CNG", label: "CNG" },
            { value: "XP", label: "XP / Premium" },
          ]}
        />
        <Input
          label="Capacity (L)"
          type="number"
          min={0}
          value={capacity}
          onChange={(e) => setCapacity(Number(e.target.value) || 0)}
          required
        />
        <Input
          label="Low threshold (L)"
          type="number"
          min={0}
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value) || 0)}
        />
      </form>
    </Modal>
  );
}

function DipReadingModal({
  tank,
  onClose,
  onSaved,
}: {
  tank: Tank | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [readingDate, setReadingDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [readingLitres, setReadingLitres] = useState(0);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!tank) return;
    setBusy(true);
    try {
      await adminApi.createDipReading(tank.id, {
        reading_date: readingDate,
        reading_litres: readingLitres,
        notes: notes.trim() || undefined,
      });
      toast.success("Dip reading recorded.");
      onSaved();
    } catch (err) {
      toast.error(errMsg(err, "Failed to save dip reading."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={!!tank}
      onClose={onClose}
      title={tank ? `Dip reading — Tank #${tank.tank_number}` : "Dip reading"}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={busy || readingLitres <= 0}
          >
            {busy ? "Saving…" : "Save"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Input
          label="Reading date"
          type="date"
          value={readingDate}
          onChange={(e) => setReadingDate(e.target.value)}
          required
        />
        <Input
          label="Litres"
          type="number"
          min={0}
          step="0.01"
          value={readingLitres}
          onChange={(e) => setReadingLitres(Number(e.target.value) || 0)}
          required
        />
        <Input
          label="Notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </form>
    </Modal>
  );
}
