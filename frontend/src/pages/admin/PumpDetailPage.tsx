import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import toast from "react-hot-toast";
import { ArrowLeft, Save, Trash2, Wrench } from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { PageHeader } from "../../components/ui/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { adminApi, Pump, Downtime } from "../../api/admin";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function PumpDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [pump, setPump] = useState<Pump | null>(null);
  const [downtimes, setDowntimes] = useState<Downtime[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancel = false;
    (async () => {
      setLoading(true);
      try {
        const p = await adminApi.getPump(id);
        if (cancel) return;
        setPump(p);
        setName(p.name);
        setLocation(p.location ?? "");
        setIsActive(p.is_active);

        const dt = await adminApi
          .getDowntimes({ pump_id: id, page: 1, page_size: 20 })
          .catch(() => ({ items: [], total: 0 }));
        if (!cancel) setDowntimes(dt.items);
      } catch (err) {
        if (!cancel) toast.error(errMsg(err, "Failed to load pump."));
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [id]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!id) return;
    setSaving(true);
    try {
      const updated = await adminApi.updatePump(id, {
        name: name.trim(),
        location: location.trim() || undefined,
        is_active: isActive,
      });
      setPump(updated);
      toast.success("Pump updated.");
    } catch (err) {
      toast.error(errMsg(err, "Failed to update pump."));
    } finally {
      setSaving(false);
    }
  }

  async function onDelete() {
    if (!id) return;
    try {
      await adminApi.deletePump(id);
      toast.success("Pump deleted.");
      navigate("/admin/pumps");
    } catch (err) {
      toast.error(errMsg(err, "Failed to delete pump."));
    }
  }

  if (loading) {
    return (
      <div className="py-10">
        <Spinner label="Loading pump…" />
      </div>
    );
  }
  if (!pump) {
    return <div className="text-slate-500 text-sm">Pump not found.</div>;
  }

  return (
    <div className="space-y-6">
      <Link
        to="/admin/pumps"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" /> All pumps
      </Link>

      <PageHeader
        title={pump.name}
        description={pump.location ?? "No location set"}
        actions={
          <>
            <Badge tone={pump.is_active ? "green" : "slate"}>
              {pump.is_active ? "Active" : "Inactive"}
            </Badge>
            <Button
              variant="danger"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="h-4 w-4" /> Delete
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <h3 className="font-semibold mb-4 text-slate-900">Edit pump</h3>
          <form onSubmit={onSave} className="space-y-4">
            <Input
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <Input
              label="Location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded border-slate-300"
              />
              Active
            </label>
            <Button type="submit" disabled={saving} className="w-full">
              <Save className="h-4 w-4" />
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </form>
        </Card>

        <Card className="lg:col-span-2">
          <h3 className="font-semibold mb-4 text-slate-900">
            Nozzles ({pump.nozzles?.length ?? pump.nozzle_count})
          </h3>
          {pump.nozzles && pump.nozzles.length > 0 ? (
            <ul className="divide-y divide-slate-100">
              {pump.nozzles.map((n) => (
                <li
                  key={n.id}
                  className="py-2.5 flex items-center justify-between text-sm"
                >
                  <div>
                    <div className="font-medium text-slate-900">
                      Nozzle #{n.nozzle_number}
                    </div>
                    <div className="text-xs text-slate-500">
                      {n.product_name ?? n.fuel_type}
                    </div>
                  </div>
                  <Badge tone="blue">{n.fuel_type}</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-slate-500">
              No nozzles configured.
            </div>
          )}
        </Card>
      </div>

      <Card>
        <h3 className="font-semibold mb-4 text-slate-900 flex items-center gap-2">
          <Wrench className="h-4 w-4" /> Maintenance history
        </h3>
        {downtimes.length === 0 ? (
          <div className="text-sm text-slate-500">
            No maintenance records yet.
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {downtimes.map((d) => (
              <li key={d.id} className="py-2.5 text-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-slate-900">
                      {d.reason_type}
                    </div>
                    {d.description && (
                      <div className="text-xs text-slate-500">
                        {d.description}
                      </div>
                    )}
                  </div>
                  <Badge tone={d.ended_at ? "green" : "amber"}>
                    {d.ended_at ? "Closed" : "Open"}
                  </Badge>
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  {new Date(d.started_at).toLocaleString()} →{" "}
                  {d.ended_at ? new Date(d.ended_at).toLocaleString() : "now"}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete pump?"
        message="This soft-deletes the pump. Shifts, nozzles, and history remain intact but the pump is removed from active lists."
        confirmLabel="Delete"
        destructive
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async () => {
          setConfirmDelete(false);
          await onDelete();
        }}
      />
    </div>
  );
}
