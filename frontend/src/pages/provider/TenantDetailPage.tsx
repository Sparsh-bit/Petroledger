import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import {
  ArrowLeft,
  Lock,
  LockOpen,
  Users,
  Building2,
  CreditCard,
  AlertOctagon,
  Trash2,
} from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { PageHeader } from "../../components/ui/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import { providerApi, TenantDetail } from "../../api/provider";

const PLANS = ["BASIC", "PRO", "ENTERPRISE"];
const STATUSES = ["active", "trialing", "past_due", "cancelled"];

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [plan, setPlan] = useState("BASIC");
  const [status, setStatus] = useState("active");
  const [expires, setExpires] = useState("");
  const [price, setPrice] = useState(0);
  const [pendingLock, setPendingLock] = useState(false);
  const [lockBusy, setLockBusy] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);

  async function load() {
    if (!id) return;
    setLoading(true);
    try {
      const d = await providerApi.getTenant(id);
      setData(d);
      setPlan(d.summary.subscription_plan);
      setStatus(d.summary.subscription_status);
      setExpires(
        d.summary.subscription_expires_at
          ? d.summary.subscription_expires_at.slice(0, 10)
          : "",
      );
      setPrice(d.summary.monthly_price_inr);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load tenant."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function saveSubscription(e: FormEvent) {
    e.preventDefault();
    if (!id) return;
    setSaving(true);
    try {
      await providerApi.updateSubscription(id, {
        plan,
        status,
        expires_at: expires ? new Date(expires).toISOString() : null,
        monthly_price_inr: price,
      });
      toast.success("Subscription updated.");
      await load();
    } catch (err) {
      toast.error(errMsg(err, "Failed to update subscription."));
    } finally {
      setSaving(false);
    }
  }

  async function confirmLockToggle() {
    if (!id || !data) return;
    setLockBusy(true);
    try {
      if (data.summary.is_locked) {
        await providerApi.unlockTenant(id);
        toast.success("Tenant unlocked.");
      } else {
        await providerApi.lockTenant(id);
        toast.success("Tenant locked.");
      }
      setPendingLock(false);
      void load();
    } catch (err) {
      toast.error(errMsg(err, "Failed to toggle lock."));
    } finally {
      setLockBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="py-10">
        <Spinner label="Loading tenant…" />
      </div>
    );
  }
  if (!data) {
    return <div className="text-sm text-slate-500">Tenant not found.</div>;
  }

  const s = data.summary;

  return (
    <div className="space-y-6">
      <Link
        to="/provider/tenants"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" /> All tenants
      </Link>

      <PageHeader
        title={s.name}
        description={s.owner_email}
        actions={
          <>
            <Badge tone="indigo">{s.subscription_plan}</Badge>
            {s.is_locked ? (
              <Badge tone="red">Locked</Badge>
            ) : (
              <Badge tone="green">
                {s.subscription_status || "active"}
              </Badge>
            )}
            <Button
              variant={s.is_locked ? "secondary" : "danger"}
              onClick={() => setPendingLock(true)}
            >
              {s.is_locked ? (
                <>
                  <LockOpen className="h-4 w-4" /> Unlock
                </>
              ) : (
                <>
                  <Lock className="h-4 w-4" /> Lock
                </>
              )}
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <CreditCard className="h-4 w-4 text-indigo-500" /> Subscription
          </h3>
          <form onSubmit={saveSubscription} className="space-y-4">
            <Select
              label="Plan"
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
              options={PLANS.map((p) => ({ value: p, label: p }))}
            />
            <Select
              label="Status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              options={STATUSES.map((s) => ({ value: s, label: s }))}
            />
            <Input
              label="Next billing"
              type="date"
              value={expires}
              onChange={(e) => setExpires(e.target.value)}
            />
            <Input
              label="Monthly price (INR)"
              type="number"
              value={price}
              onChange={(e) => setPrice(Number(e.target.value) || 0)}
            />
            <Button type="submit" disabled={saving} className="w-full">
              {saving ? "Saving…" : "Save subscription"}
            </Button>
          </form>
        </Card>

        <Card className="lg:col-span-2">
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Users className="h-4 w-4 text-indigo-500" /> Users (
            {data.users.length})
          </h3>
          <div className="divide-y divide-slate-100">
            {data.users.map((u) => (
              <div
                key={u.id}
                className="py-2.5 flex items-center justify-between text-sm"
              >
                <div>
                  <div className="font-medium text-slate-900">{u.email}</div>
                  <div className="text-xs text-slate-500">
                    {u.role} · last login{" "}
                    {u.last_login
                      ? new Date(u.last_login).toLocaleString()
                      : "never"}
                  </div>
                </div>
                <Badge tone={u.is_active ? "green" : "slate"}>
                  {u.is_active ? "active" : "inactive"}
                </Badge>
              </div>
            ))}
            {data.users.length === 0 && (
              <div className="py-3 text-sm text-slate-500">No users.</div>
            )}
          </div>

          <h3 className="font-semibold text-slate-900 mt-6 mb-4 flex items-center gap-2">
            <Building2 className="h-4 w-4 text-indigo-500" /> Pumps (
            {data.pumps.length})
          </h3>
          <div className="divide-y divide-slate-100">
            {data.pumps.map((p) => (
              <div
                key={p.id}
                className="py-2.5 flex items-center justify-between text-sm"
              >
                <div>
                  <div className="font-medium text-slate-900">{p.name}</div>
                  <div className="text-xs font-mono text-slate-500">
                    {p.code ?? "no code"}
                  </div>
                </div>
                <Badge tone={p.is_active ? "green" : "slate"}>
                  {p.is_active ? "active" : "inactive"}
                </Badge>
              </div>
            ))}
            {data.pumps.length === 0 && (
              <div className="py-3 text-sm text-slate-500">No pumps.</div>
            )}
          </div>
        </Card>
      </div>

      <Card className="border-red-200 bg-red-50/40">
        <h3 className="font-semibold text-red-700 mb-2 flex items-center gap-2">
          <AlertOctagon className="h-4 w-4" /> Danger zone
        </h3>
        <p className="text-sm text-slate-600 mb-4">
          Permanently delete this tenant and every record it owns — users,
          pumps, shifts, transactions and audit logs. This cannot be undone.
        </p>
        <Button
          variant="danger"
          onClick={() => {
            setDeleteConfirm("");
            setShowDelete(true);
          }}
        >
          <Trash2 className="h-4 w-4" /> Delete tenant permanently
        </Button>
      </Card>

      <ConfirmDialog
        open={pendingLock}
        title={s.is_locked ? "Unlock tenant?" : "Lock tenant?"}
        message={
          s.is_locked
            ? `Unlocking ${s.name} restores API access for all users.`
            : `Locking ${s.name} blocks all its users immediately.`
        }
        destructive={!s.is_locked}
        busy={lockBusy}
        confirmLabel={s.is_locked ? "Unlock" : "Lock"}
        onCancel={() => setPendingLock(false)}
        onConfirm={confirmLockToggle}
      />

      <Modal
        open={showDelete}
        onClose={() => (deleting ? undefined : setShowDelete(false))}
        title="Permanently delete tenant"
        widthClass="max-w-md"
      >
        <div className="space-y-3">
          <p className="text-sm text-slate-700">
            This removes <span className="font-semibold">{s.name}</span> and
            every record it owns — users, pumps, shifts, transactions, audit
            logs — forever. There is no undo.
          </p>
          <p className="text-sm text-slate-700">
            Type the tenant name below to confirm.
          </p>
          <Input
            label={`Type "${s.name}" to confirm`}
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder={s.name}
            autoFocus
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button
            variant="secondary"
            onClick={() => setShowDelete(false)}
            disabled={deleting}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={deleting || deleteConfirm.trim() !== s.name.trim()}
            onClick={async () => {
              if (!id) return;
              setDeleting(true);
              try {
                await providerApi.deleteTenant(id, deleteConfirm.trim());
                toast.success(`Tenant "${s.name}" deleted.`);
                navigate("/provider/tenants", { replace: true });
              } catch (err) {
                toast.error(errMsg(err, "Failed to delete tenant."));
              } finally {
                setDeleting(false);
              }
            }}
          >
            {deleting ? "Deleting…" : "Delete permanently"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
