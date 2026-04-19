import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { Activity } from "lucide-react";
import { Badge, Input } from "../../components/ui";
import { Select } from "../../components/ui/Select";
import { DataTable, Pagination } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, Shift, Pump, Worker } from "../../api/admin";
import { useOrgStore } from "../../store/org";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export function statusBadgeTone(status: string): "green" | "amber" | "blue" | "red" | "slate" {
  const s = status.toUpperCase();
  if (s === "RECONCILED" || s === "LOCKED") return "green";
  if (s === "COMPLETED") return "amber";
  if (s === "ACTIVE") return "blue";
  if (s === "FLAGGED") return "red";
  return "slate";
}

const STATUSES = ["", "ACTIVE", "COMPLETED", "RECONCILED", "LOCKED"];

export default function ShiftsPage() {
  const navigate = useNavigate();
  const { selectedOrgId } = useOrgStore();
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [pumps, setPumps] = useState<Pump[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pumpId, setPumpId] = useState("");
  const [workerId, setWorkerId] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const pageSize = 25;

  async function load() {
    setLoading(true);
    try {
      const res = await adminApi.getShifts({
        org_id: selectedOrgId ?? undefined,
        pump_id: pumpId || undefined,
        worker_id: workerId || undefined,
        status: status || undefined,
        page,
        page_size: pageSize,
      });
      setShifts(res.items);
      setTotal(res.total);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load shifts."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // load pumps + workers once for filter/label maps
    void (async () => {
      try {
        const [p, w] = await Promise.all([
          adminApi.getPumps({
            org_id: selectedOrgId ?? undefined,
            page: 1,
            page_size: 100,
          }),
          adminApi.getWorkers({
            org_id: selectedOrgId ?? undefined,
            page: 1,
            page_size: 200,
          }),
        ]);
        setPumps(p.items);
        setWorkers(w.items);
      } catch {
        /* best effort */
      }
    })();
  }, [selectedOrgId]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgId, pumpId, workerId, status, page]);

  const pumpName = useMemo(() => {
    const m = new Map(pumps.map((p) => [p.id, p.name]));
    return (id: string) => m.get(id) ?? id.slice(0, 8);
  }, [pumps]);
  const workerCode = useMemo(() => {
    const m = new Map(workers.map((w) => [w.id, w.employee_code]));
    return (id: string) => m.get(id) ?? id.slice(0, 8);
  }, [workers]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Shifts"
        description="Every shift recorded across your pumps."
      />

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
        <Select
          label="Pump"
          value={pumpId}
          onChange={(e) => {
            setPumpId(e.target.value);
            setPage(1);
          }}
          placeholder="All pumps"
          options={pumps.map((p) => ({ value: p.id, label: p.name }))}
        />
        <Select
          label="Worker"
          value={workerId}
          onChange={(e) => {
            setWorkerId(e.target.value);
            setPage(1);
          }}
          placeholder="All workers"
          options={workers.map((w) => ({
            value: w.id,
            label: w.employee_code,
          }))}
        />
        <Select
          label="Status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          {STATUSES.filter(Boolean).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Input
          label="From (today)"
          type="date"
          disabled
          placeholder="—"
          title="Date range filter — backend to be wired"
        />
      </div>

      <DataTable<Shift>
        loading={loading}
        data={shifts}
        rowKey={(s) => s.id}
        onRowClick={(s) => navigate(`/admin/shifts/${s.id}`)}
        emptyState={
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <Activity className="h-6 w-6 text-slate-400" />
            <span>No shifts for the current filters.</span>
          </div>
        }
        columns={[
          {
            key: "date",
            header: "Date",
            render: (s) => new Date(s.start_time).toLocaleString(),
          },
          {
            key: "pump",
            header: "Pump",
            render: (s) => pumpName(s.pump_id),
          },
          {
            key: "worker",
            header: "Worker",
            render: (s) => workerCode(s.worker_id),
          },
          {
            key: "slot",
            header: "Slot",
            render: (s) => s.slot ?? "—",
          },
          {
            key: "status",
            header: "Status",
            render: (s) => (
              <Badge tone={statusBadgeTone(s.status)}>{s.status}</Badge>
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
    </div>
  );
}
