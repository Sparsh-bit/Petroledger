import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Fuel, Trash2 } from "lucide-react";
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
  const queryClient = useQueryClient();
  const { selectedOrgId } = useOrgStore();
  useEnsureOrgs();
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const pageSize = 25;

  const pumpsQuery = useQuery({
    queryKey: ["pumps", { orgId: selectedOrgId ?? null, page, pageSize }],
    queryFn: () =>
      adminApi.getPumps({
        org_id: selectedOrgId ?? undefined,
        page,
        page_size: pageSize,
      }),
    placeholderData: (prev) => prev,
  });

  const pumps = pumpsQuery.data?.items ?? [];
  const total = pumpsQuery.data?.total ?? 0;
  const loading = pumpsQuery.isPending;

  if (pumpsQuery.error) {
    // One-shot toast on transient failures — the query retries once on its own.
    const msg = errMsg(pumpsQuery.error, "Failed to load pumps.");
    if (msg) toast.error(msg);
  }

  async function onDeletePump(p: Pump) {
    if (!window.confirm(`Delete pump "${p.name}"? This cannot be undone.`)) {
      return;
    }
    setDeletingId(p.id);
    try {
      await adminApi.deletePump(p.id);
      toast.success(`Pump "${p.name}" deleted.`);
      await queryClient.invalidateQueries({ queryKey: ["pumps"] });
    } catch (err) {
      toast.error(errMsg(err, "Failed to delete pump."));
    } finally {
      setDeletingId(null);
    }
  }

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
          {
            key: "actions",
            header: "",
            render: (p) => (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  void onDeletePump(p);
                }}
                disabled={deletingId === p.id}
                title="Delete pump"
                className="inline-flex items-center justify-center h-8 w-8 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
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

      <CreatePumpModal
        open={createOpen}
        orgId={selectedOrgId}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          setCreateOpen(false);
          void queryClient.invalidateQueries({ queryKey: ["pumps"] });
        }}
      />
    </div>
  );
}

type FuelType = "petrol" | "diesel" | "cng";

const FUEL_OPTIONS: { value: FuelType; label: string; tone: string }[] = [
  { value: "petrol", label: "Petrol (MS)", tone: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  { value: "diesel", label: "Diesel (HSD)", tone: "text-amber-700 bg-amber-50 border-amber-200" },
  { value: "cng", label: "CNG", tone: "text-sky-700 bg-sky-50 border-sky-200" },
];

function clampNozzles(
  n: number,
  existing: FuelType[],
  fallback: FuelType = "petrol",
): FuelType[] {
  const safe = Math.max(0, Math.min(20, n));
  if (safe === existing.length) return existing;
  if (safe < existing.length) return existing.slice(0, safe);
  const extra = Array.from({ length: safe - existing.length }, () => fallback);
  return [...existing, ...extra];
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
  const [nozzleFuels, setNozzleFuels] = useState<FuelType[]>(["petrol", "diesel"]);
  const [busy, setBusy] = useState(false);

  function setCount(n: number) {
    setNozzleCount(n);
    setNozzleFuels((prev) => clampNozzles(n, prev));
  }

  function setFuel(idx: number, fuel: FuelType) {
    setNozzleFuels((prev) => prev.map((f, i) => (i === idx ? fuel : f)));
  }

  function resetForm() {
    setName("");
    setLocation("");
    setCount(2);
    setNozzleFuels(["petrol", "diesel"]);
  }

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
        nozzles: nozzleFuels.map((fuel_type, i) => ({
          nozzle_number: i + 1,
          fuel_type,
        })),
      });
      // Backend may have self-healed by creating a default org — pull the
      // fresh list so downstream pages (dashboard, shifts, etc.) see it.
      await refreshOrgs();
      toast.success(`Pump "${name.trim()}" created with ${nozzleCount} nozzle(s).`);
      resetForm();
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
      widthClass="max-w-lg"
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
          onChange={(e) => setCount(Number(e.target.value) || 0)}
          required
        />

        {nozzleCount > 0 && (
          <div className="space-y-2">
            <label className="block text-[11px] font-semibold uppercase tracking-widest text-slate-500">
              Fuel per nozzle
            </label>
            <div className="space-y-2">
              {nozzleFuels.map((fuel, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2"
                >
                  <span className="text-xs font-semibold text-slate-500 w-16 shrink-0">
                    Nozzle {i + 1}
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {FUEL_OPTIONS.map((opt) => {
                      const active = fuel === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setFuel(i, opt.value)}
                          className={`px-2.5 py-1 rounded-full border text-[11px] font-bold uppercase tracking-wide transition ${
                            active
                              ? opt.tone
                              : "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
                          }`}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-slate-400">
              Each nozzle must be tagged so later readings route to the right fuel.
            </p>
          </div>
        )}
      </form>
    </Modal>
  );
}
