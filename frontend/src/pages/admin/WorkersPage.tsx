import { FormEvent, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Copy, Plus, Search, UserRound } from "lucide-react";
import { Badge, Button, Input } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { DataTable, Pagination } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, InviteManagerResponse, Pump, Worker } from "../../api/admin";
import { useOrgStore, useEnsureOrgs } from "../../store/org";
import { errMsg } from "../../lib/errMsg";


export default function WorkersPage() {
  const { selectedOrgId } = useOrgStore();
  useEnsureOrgs();
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [pumps, setPumps] = useState<Pump[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [inviteManagerOpen, setInviteManagerOpen] = useState(false);
  const pageSize = 25;

  async function load() {
    setLoading(true);
    try {
      const [workersRes, pumpsRes] = await Promise.all([
        adminApi.getWorkers({
          org_id: selectedOrgId ?? undefined,
          page,
          page_size: pageSize,
        }),
        adminApi.getPumps({
          org_id: selectedOrgId ?? undefined,
          page: 1,
          page_size: 100,
        }),
      ]);
      setWorkers(Array.isArray(workersRes) ? workersRes : workersRes?.items ?? []);
      setTotal(workersRes?.total ?? 0);
      setPumps(Array.isArray(pumpsRes) ? pumpsRes : pumpsRes?.items ?? []);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load workers."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgId, page]);

  const pumpName = useMemo(() => {
    const map = new Map(pumps.map((p) => [p.id, p.name]));
    return (id: string) => map.get(id) ?? id.slice(0, 8);
  }, [pumps]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return workers;
    return workers.filter((w) =>
      w.employee_code.toLowerCase().includes(term),
    );
  }, [workers, q]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Workers"
        description="Workforce profiles assigned to pumps."
        actions={
          <div className="flex gap-2">
            <Button
              variant="ghost"
              onClick={() => setInviteManagerOpen(true)}
            >
              <Plus className="h-4 w-4" /> Add manager
            </Button>
            <Button
              onClick={() => setCreateOpen(true)}
              disabled={pumps.length === 0}
            >
              <Plus className="h-4 w-4" /> Add worker
            </Button>
          </div>
        }
      />

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            className="pl-9"
            placeholder="Search by employee code…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </div>

      <DataTable<Worker>
        loading={loading}
        data={filtered}
        rowKey={(w) => w.id}
        emptyState={
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <UserRound className="h-6 w-6 text-slate-400" />
            <span>No workers yet.</span>
          </div>
        }
        columns={[
          {
            key: "code",
            header: "Employee Code",
            render: (w) => (
              <span className="font-mono text-slate-900">
                {w.employee_code}
              </span>
            ),
          },
          {
            key: "name",
            header: "Full Name",
            render: (w) => w.full_name || "—",
          },
          {
            key: "pump",
            header: "Pump",
            render: (w) => pumpName(w.pump_id),
          },
          {
            key: "joined",
            header: "Joined",
            render: (w) =>
              w.joined_date
                ? new Date(w.joined_date).toLocaleDateString()
                : "—",
          },
          {
            key: "status",
            header: "Status",
            render: (w) => (
              <Badge tone={w.is_active === false ? "slate" : "green"}>
                {w.is_active === false ? "Inactive" : "Active"}
              </Badge>
            ),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (w) => (
              <button
                type="button"
                onClick={async () => {
                  try {
                    await adminApi.updateWorker(w.id, {
                      is_active: w.is_active === false,
                    });
                    toast.success(
                      w.is_active === false
                        ? "Worker reactivated."
                        : "Worker deactivated.",
                    );
                    void load();
                  } catch (err) {
                    toast.error(errMsg(err, "Update failed."));
                  }
                }}
                className="text-xs text-indigo-600 hover:text-indigo-500"
              >
                {w.is_active === false ? "Reactivate" : "Deactivate"}
              </button>
            ),
          },
        ]}
      />

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
      />

      <CreateWorkerModal
        open={createOpen}
        pumps={pumps}
        orgId={selectedOrgId}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          void load();
        }}
      />

      <InviteManagerModal
        open={inviteManagerOpen}
        orgId={selectedOrgId}
        onClose={() => setInviteManagerOpen(false)}
      />
    </div>
  );
}

function InviteManagerModal({
  open,
  orgId,
  onClose,
}: {
  open: boolean;
  orgId: string | null;
  onClose: () => void;
}) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<InviteManagerResponse | null>(null);

  function reset() {
    setFullName("");
    setEmail("");
    setPhone("");
    setResult(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!orgId) {
      toast.error("No organisation selected.");
      return;
    }
    setBusy(true);
    try {
      const res = await adminApi.inviteManager({
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim(),
        org_id: orgId,
      });
      setResult(res);
    } catch (err) {
      toast.error(errMsg(err, "Failed to invite manager."));
    } finally {
      setBusy(false);
    }
  }

  function handleClose() {
    reset();
    onClose();
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Add manager"
      widthClass="max-w-lg"
      footer={
        result ? (
          <Button onClick={handleClose}>Done</Button>
        ) : (
          <>
            <Button variant="ghost" onClick={handleClose} disabled={busy}>
              Cancel
            </Button>
            <Button
              onClick={(e) => void onSubmit(e as unknown as FormEvent)}
              disabled={
                busy ||
                !fullName.trim() ||
                !email.trim() ||
                phone.trim().length !== 10
              }
            >
              {busy ? "Inviting…" : "Invite"}
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Manager account created for <strong>{result.email}</strong>. Share
            the temporary password below — they can change it after logging in.
          </p>
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <span className="flex-1 font-mono text-sm tracking-wide text-slate-900">
              {result.temporary_password}
            </span>
            <button
              type="button"
              onClick={() => {
                void navigator.clipboard.writeText(result.temporary_password);
                toast.success("Copied!");
              }}
              className="text-slate-400 hover:text-slate-600"
              title="Copy password"
            >
              <Copy className="h-4 w-4" />
            </button>
          </div>
          <p className="text-xs text-slate-400">
            Login URL: {window.location.origin}/login — Pump code:{" "}
            <span className="font-mono">
              (same pump code as the organisation)
            </span>
          </p>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Full name"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ravi Kumar"
            />
            <Input
              label="Email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="manager@example.com"
            />
            <Input
              label="Phone"
              type="tel"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))}
              placeholder="10-digit mobile number"
            />
          </div>
        </form>
      )}
    </Modal>
  );
}

function generateEmpCode(): string {
  const suffix = Math.random().toString(36).slice(2, 6).toUpperCase();
  return `EMP-${suffix}`;
}

function CreateWorkerModal({
  open,
  pumps,
  orgId,
  onClose,
  onCreated,
}: {
  open: boolean;
  pumps: Pump[];
  orgId: string | null;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [employeeCode, setEmployeeCode] = useState(() => generateEmpCode());
  const [pumpId, setPumpId] = useState("");
  const [joinedDate, setJoinedDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [busy, setBusy] = useState(false);

  // Regenerate a fresh unique code every time the modal opens
  useEffect(() => {
    if (open) setEmployeeCode(generateEmpCode());
  }, [open]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pumpId) {
      toast.error("Pick a pump.");
      return;
    }
    setBusy(true);
    try {
      await adminApi.createWorker({
        email: email.trim(),
        password,
        pump_id: pumpId,
        employee_code: employeeCode.trim(),
        joined_date: joinedDate,
        org_id: orgId ?? undefined,
        full_name: fullName.trim(),
      });
      toast.success("Worker created.");
      setFullName("");
      setEmail("");
      setPassword("");
      setEmployeeCode("");
      setPumpId("");
      onCreated();
    } catch (err) {
      toast.error(errMsg(err, "Failed to create worker."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add worker"
      widthClass="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={
              busy ||
              !email.trim() ||
              password.length < 8 ||
              !employeeCode.trim() ||
              !pumpId
            }
          >
            {busy ? "Creating…" : "Create"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Full name"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Ravi Kumar"
          />
          <Input
            label="Email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="worker@example.com"
          />
          <Input
            label="Password"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Minimum 8 characters"
          />
          <Input
            label="Employee code"
            required
            value={employeeCode}
            onChange={(e) => setEmployeeCode(e.target.value)}
            placeholder="EMP-001"
            hint="Auto-generated — edit if needed"
          />
          <Select
            label="Pump"
            value={pumpId}
            onChange={(e) => setPumpId(e.target.value)}
            placeholder="Select pump…"
            options={pumps.map((p) => ({ value: p.id, label: p.name }))}
          />
          <Input
            label="Joined date"
            type="date"
            value={joinedDate}
            onChange={(e) => setJoinedDate(e.target.value)}
            required
          />
        </div>
      </form>
    </Modal>
  );
}
