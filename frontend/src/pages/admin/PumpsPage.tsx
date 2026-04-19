import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { Plus, Search, Fuel } from "lucide-react";
import { Badge, Button, Input } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { DataTable, Pagination } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, Pump } from "../../api/admin";
import { useOrgStore, useEnsureOrgs, refreshOrgs } from "../../store/org";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function PumpsPage() {
  const navigate = useNavigate();
  const { selectedOrgId } = useOrgStore();
  useEnsureOrgs();
  const [pumps, setPumps] = useState<Pump[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const pageSize = 25;

  async function load() {
    setLoading(true);
    try {
      const res = await adminApi.getPumps({
        org_id: selectedOrgId ?? undefined,
        page,
        page_size: pageSize,
      });
      setPumps(res?.items ?? []);
      setTotal(res?.total ?? 0);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load pumps."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgId, page]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return pumps;
    return pumps.filter(
      (p) =>
        p.name.toLowerCase().includes(term) ||
        (p.location ?? "").toLowerCase().includes(term),
    );
  }, [pumps, q]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pumps"
        description="Manage pump hardware for this organisation."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> Add pump
          </Button>
        }
      />

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            className="pl-9"
            placeholder="Search name or location…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </div>

      <DataTable<Pump>
        loading={loading}
        data={filtered}
        rowKey={(p) => p.id}
        onRowClick={(p) => navigate(`/admin/pumps/${p.id}`)}
        emptyState={
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <Fuel className="h-6 w-6 text-slate-400" />
            <span>No pumps yet. Add your first pump to start.</span>
          </div>
        }
        columns={[
          {
            key: "name",
            header: "Name",
            render: (p) => (
              <div>
                <div className="font-medium text-slate-900">{p.name}</div>
                {p.code && (
                  <div className="text-xs font-mono text-slate-500">{p.code}</div>
                )}
              </div>
            ),
          },
          {
            key: "location",
            header: "Location",
            render: (p) => p.location ?? "—",
          },
          {
            key: "nozzles",
            header: "Nozzles",
            render: (p) => p.nozzle_count,
          },
          {
            key: "status",
            header: "Status",
            render: (p) => (
              <Badge tone={p.is_active ? "green" : "slate"}>
                {p.is_active ? "Active" : "Inactive"}
              </Badge>
            ),
          },
          {
            key: "created",
            header: "Created",
            render: (p) =>
              p.created_at
                ? new Date(p.created_at).toLocaleDateString()
                : "—",
          },
        ]}
      />

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
      />

      <CreatePumpModal
        open={createOpen}
        orgId={selectedOrgId}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          void load();
        }}
      />
    </div>
  );
}

function CreatePumpModal({
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
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [nozzleCount, setNozzleCount] = useState(2);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      // Let the backend resolve org_id. POST /pumps accepts an optional
      // org_id and falls back to the caller's tenant's first active org
      // (auto-creating a default one if none exists).
      await adminApi.createPump({
        org_id: orgId ?? undefined,
        name: name.trim(),
        location: location.trim() || undefined,
        nozzle_count: nozzleCount,
      });
      // Backend may have self-healed by creating a default org — pull the
      // fresh list so downstream pages (dashboard, shifts, etc.) see it.
      await refreshOrgs();
      toast.success("Pump created.");
      setName("");
      setLocation("");
      setNozzleCount(2);
      onCreated();
    } catch (err) {
      toast.error(errMsg(err, "Failed to create pump."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add pump"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={busy || !name.trim()}
          >
            {busy ? "Creating…" : "Create"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <Input
          label="Pump name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          placeholder="Main pump - Block A"
        />
        <Input
          label="Location"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="Highway side"
        />
        <Input
          label="Nozzle count"
          type="number"
          min={0}
          max={20}
          value={nozzleCount}
          onChange={(e) => setNozzleCount(Number(e.target.value) || 0)}
          required
        />
      </form>
    </Modal>
  );
}
