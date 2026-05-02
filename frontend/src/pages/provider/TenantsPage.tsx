import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { Building2, Lock, LockOpen, Plus, Search } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, Input } from "../../components/ui";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { PageHeader } from "../../components/ui/PageHeader";
import { DataTable } from "../../components/ui/DataTable";
import { providerApi, TenantSummary } from "../../api/provider";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

function fmtMoney(v: number): string {
  return `₹${v.toLocaleString("en-IN")}`;
}

interface CreateForm {
  tenant_name: string;
  owner_name: string;
  owner_email: string;
  password: string;
}

const EMPTY_CREATE_FORM: CreateForm = {
  tenant_name: "",
  owner_name: "",
  owner_email: "",
  password: "",
};

export default function TenantsPage() {
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const [plan, setPlan] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [pendingLock, setPendingLock] = useState<TenantSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(EMPTY_CREATE_FORM);
  const [creating, setCreating] = useState(false);

  const tenantsQ = useQuery({
    queryKey: ["tenants"],
    queryFn: () => providerApi.getTenants(),
    placeholderData: (prev) => prev,
  });

  const tenants: TenantSummary[] = tenantsQ.data ?? [];
  const loading = tenantsQ.isPending;

  async function load() {
    await queryClient.invalidateQueries({ queryKey: ["tenants"] });
  }

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return tenants.filter((t) => {
      if (plan && t.subscription_plan !== plan) return false;
      if (statusFilter === "active" && (t.is_locked || !t.is_active))
        return false;
      if (statusFilter === "locked" && !t.is_locked) return false;
      if (!term) return true;
      return (
        t.name.toLowerCase().includes(term) ||
        t.owner_email.toLowerCase().includes(term)
      );
    });
  }, [tenants, q, plan, statusFilter]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (creating) return;
    setCreating(true);
    try {
      await providerApi.createTenant({
        tenant_name: createForm.tenant_name.trim(),
        owner_name: createForm.owner_name.trim(),
        owner_email: createForm.owner_email.trim().toLowerCase(),
        owner_phone: "",
        password: createForm.password,
      });
      toast.success(
        `Tenant created. Credentials emailed to ${createForm.owner_email.trim()}.`,
        { duration: 6000 },
      );
      setShowCreate(false);
      setCreateForm(EMPTY_CREATE_FORM);
      void load();
    } catch (err) {
      toast.error(errMsg(err, "Failed to create tenant."));
    } finally {
      setCreating(false);
    }
  }

  async function confirmLock() {
    if (!pendingLock) return;
    setBusy(true);
    try {
      if (pendingLock.is_locked) {
        await providerApi.unlockTenant(pendingLock.tenant_id);
        toast.success("Tenant unlocked.");
      } else {
        await providerApi.lockTenant(pendingLock.tenant_id);
        toast.success("Tenant locked.");
      }
      setPendingLock(null);
      void load();
    } catch (err) {
      toast.error(errMsg(err, "Failed to toggle lock."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tenants"
        description="Manage every dealer tenant on the platform."
        actions={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" /> Create tenant
          </Button>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <div className="relative sm:col-span-2">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            className="pl-9"
            placeholder="Search name or owner email…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
        <Select
          value={plan}
          onChange={(e) => setPlan(e.target.value)}
          placeholder="All plans"
          options={[
            { value: "BASIC", label: "Basic" },
            { value: "PRO", label: "Pro" },
            { value: "ENTERPRISE", label: "Enterprise" },
          ]}
        />
        <Select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          placeholder="All statuses"
          options={[
            { value: "active", label: "Active" },
            { value: "locked", label: "Locked" },
          ]}
        />
      </div>

      <DataTable<TenantSummary>
        data={filtered}
        loading={loading}
        rowKey={(t) => t.tenant_id}
        emptyState={
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <Building2 className="h-6 w-6 text-slate-400" />
            <span>No tenants match the filters.</span>
          </div>
        }
        columns={[
          {
            key: "name",
            header: "Name",
            render: (t) => (
              <div>
                <Link
                  to={`/provider/tenants/${t.tenant_id}`}
                  className="font-medium text-slate-900 hover:text-indigo-600"
                >
                  {t.name}
                </Link>
                <div className="text-xs text-slate-500">{t.owner_email}</div>
              </div>
            ),
          },
          {
            key: "plan",
            header: "Plan",
            render: (t) => <Badge tone="indigo">{t.subscription_plan}</Badge>,
          },
          {
            key: "revenue",
            header: "Monthly",
            render: (t) => fmtMoney(t.monthly_price_inr),
          },
          {
            key: "orgs",
            header: "Orgs",
            render: (t) => t.org_count,
          },
          {
            key: "users",
            header: "Users",
            render: (t) => t.user_count,
          },
          {
            key: "status",
            header: "Status",
            render: (t) =>
              t.is_locked ? (
                <Badge tone="red">Locked</Badge>
              ) : (
                <Badge tone="green">
                  {t.subscription_status || "active"}
                </Badge>
              ),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (t) => (
              <div className="flex items-center justify-end gap-2">
                <Link
                  to={`/provider/tenants/${t.tenant_id}`}
                  className="text-xs text-slate-500 hover:text-slate-900"
                >
                  View
                </Link>
                <Button
                  variant={t.is_locked ? "secondary" : "danger"}
                  onClick={() => setPendingLock(t)}
                  className="py-1.5 px-3 text-xs"
                >
                  {t.is_locked ? (
                    <>
                      <LockOpen className="h-3.5 w-3.5" /> Unlock
                    </>
                  ) : (
                    <>
                      <Lock className="h-3.5 w-3.5" /> Lock
                    </>
                  )}
                </Button>
              </div>
            ),
          },
        ]}
      />

      <Modal
        open={showCreate}
        onClose={() => (creating ? undefined : setShowCreate(false))}
        title="Create a new tenant"
        widthClass="max-w-xl"
      >
        <form
          id="create-tenant-form"
          onSubmit={handleCreate}
          className="space-y-3"
        >
          <Input
            label="Tenant / Dealer name"
            required
            value={createForm.tenant_name}
            onChange={(e) =>
              setCreateForm((f) => ({ ...f, tenant_name: e.target.value }))
            }
            placeholder="e.g. Sharma Fuels Pvt Ltd"
          />
          <Input
            label="Owner name"
            required
            value={createForm.owner_name}
            onChange={(e) =>
              setCreateForm((f) => ({ ...f, owner_name: e.target.value }))
            }
          />
          <Input
            label="Owner email"
            type="email"
            required
            value={createForm.owner_email}
            onChange={(e) =>
              setCreateForm((f) => ({ ...f, owner_email: e.target.value }))
            }
          />
          <Input
            label="Owner password"
            type="password"
            required
            minLength={8}
            value={createForm.password}
            onChange={(e) =>
              setCreateForm((f) => ({ ...f, password: e.target.value }))
            }
            placeholder="At least 8 characters"
          />
        </form>
        <div className="flex justify-end gap-2 pt-2">
          <Button
            variant="secondary"
            onClick={() => setShowCreate(false)}
            disabled={creating}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            form="create-tenant-form"
            disabled={creating}
          >
            {creating ? "Creating…" : "Create tenant"}
          </Button>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!pendingLock}
        title={pendingLock?.is_locked ? "Unlock tenant?" : "Lock tenant?"}
        message={
          pendingLock?.is_locked
            ? `Unlocking ${pendingLock?.name} restores access for all its users.`
            : `Locking ${pendingLock?.name} blocks all its users from the API immediately.`
        }
        destructive={!pendingLock?.is_locked}
        busy={busy}
        confirmLabel={pendingLock?.is_locked ? "Unlock" : "Lock"}
        onCancel={() => setPendingLock(null)}
        onConfirm={confirmLock}
      />
    </div>
  );
}
