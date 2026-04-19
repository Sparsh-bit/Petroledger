import { FormEvent, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Plus, Wrench, CheckCircle2 } from "lucide-react";
import { Badge, Button, Input } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { DataTable } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, Downtime, Pump } from "../../api/admin";
import { useOrgStore } from "../../store/org";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

const REASON_TYPES = [
  "POWER_OUTAGE",
  "EQUIPMENT_FAILURE",
  "MAINTENANCE",
  "CALIBRATION",
  "REFUEL_DELAY",
  "OTHER",
];

export default function MaintenancePage() {
  const { selectedOrgId } = useOrgStore();
  const [downtimes, setDowntimes] = useState<Downtime[]>([]);
  const [pumps, setPumps] = useState<Pump[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [onlyOpen, setOnlyOpen] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [dt, p] = await Promise.all([
        adminApi.getDowntimes({
          org_id: selectedOrgId ?? undefined,
          open_only: onlyOpen,
          page: 1,
          page_size: 100,
        }),
        adminApi.getPumps({
          org_id: selectedOrgId ?? undefined,
          page: 1,
          page_size: 100,
        }),
      ]);
      setDowntimes(dt.items);
      setPumps(p.items);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load maintenance."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgId, onlyOpen]);

  const pumpName = useMemo(() => {
    const m = new Map(pumps.map((p) => [p.id, p.name]));
    return (id: string) => m.get(id) ?? id.slice(0, 8);
  }, [pumps]);

  async function endIt(d: Downtime) {
    try {
      await adminApi.endDowntime(d.id);
      toast.success("Downtime closed.");
      void load();
    } catch (err) {
      toast.error(errMsg(err, "Failed to close downtime."));
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Maintenance"
        description="Track pump downtime and planned service windows."
        actions={
          <Button
            onClick={() => setCreateOpen(true)}
            disabled={pumps.length === 0}
          >
            <Plus className="h-4 w-4" /> Start downtime
          </Button>
        }
      />

      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={onlyOpen}
            onChange={(e) => setOnlyOpen(e.target.checked)}
            className="rounded border-slate-300"
          />
          Open only
        </label>
      </div>

      <DataTable<Downtime>
        data={downtimes}
        loading={loading}
        rowKey={(d) => d.id}
        emptyState={
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <Wrench className="h-6 w-6 text-slate-400" />
            <span>No downtime records.</span>
          </div>
        }
        columns={[
          {
            key: "pump",
            header: "Pump",
            render: (d) => pumpName(d.pump_id),
          },
          {
            key: "reason",
            header: "Reason",
            render: (d) => d.reason_type,
          },
          {
            key: "description",
            header: "Description",
            render: (d) => d.description ?? "—",
          },
          {
            key: "started",
            header: "Started",
            render: (d) => new Date(d.started_at).toLocaleString(),
          },
          {
            key: "ended",
            header: "Ended",
            render: (d) =>
              d.ended_at ? new Date(d.ended_at).toLocaleString() : "—",
          },
          {
            key: "status",
            header: "Status",
            render: (d) => (
              <Badge tone={d.ended_at ? "green" : "amber"}>
                {d.ended_at ? "Closed" : "Open"}
              </Badge>
            ),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (d) =>
              d.ended_at ? null : (
                <button
                  type="button"
                  onClick={() => void endIt(d)}
                  className="inline-flex items-center gap-1 text-xs text-emerald-600 hover:text-emerald-500"
                >
                  <CheckCircle2 className="h-3 w-3" /> Mark closed
                </button>
              ),
          },
        ]}
      />

      <CreateDowntimeModal
        open={createOpen}
        pumps={pumps}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          void load();
        }}
      />
    </div>
  );
}

function CreateDowntimeModal({
  open,
  pumps,
  onClose,
  onCreated,
}: {
  open: boolean;
  pumps: Pump[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [pumpId, setPumpId] = useState("");
  const [reason, setReason] = useState("MAINTENANCE");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pumpId) {
      toast.error("Pick a pump.");
      return;
    }
    setBusy(true);
    try {
      await adminApi.startDowntime({
        pump_id: pumpId,
        reason_type: reason,
        description: description.trim() || undefined,
      });
      toast.success("Downtime opened.");
      setPumpId("");
      setReason("MAINTENANCE");
      setDescription("");
      onCreated();
    } catch (err) {
      toast.error(errMsg(err, "Failed to start downtime."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Start downtime"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={busy || !pumpId}
          >
            {busy ? "Starting…" : "Start"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Select
          label="Pump"
          value={pumpId}
          onChange={(e) => setPumpId(e.target.value)}
          placeholder="Select pump…"
          options={pumps.map((p) => ({ value: p.id, label: p.name }))}
        />
        <Select
          label="Reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          options={REASON_TYPES.map((r) => ({
            value: r,
            label: r.replace(/_/g, " ").toLowerCase(),
          }))}
        />
        <Input
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </form>
    </Modal>
  );
}
