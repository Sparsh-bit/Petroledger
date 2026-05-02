import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { Activity, Play, StopCircle } from "lucide-react";
import { Badge, Button, Input } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { DataTable, Pagination } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, Pump, Shift, Worker, Nozzle } from "../../api/admin";
import { shiftsApi } from "../../api/shifts";
import { statusBadgeTone } from "../admin/ShiftsPage";
import { errMsg } from "../../lib/errMsg";


export default function ManagerShiftsPage() {
  const navigate = useNavigate();
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [pumps, setPumps] = useState<Pump[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [startOpen, setStartOpen] = useState(false);
  const [closeShift, setCloseShift] = useState<Shift | null>(null);
  const pageSize = 25;

  async function loadAll() {
    setLoading(true);
    try {
      const [shiftsRes, pumpsRes, workersRes] = await Promise.all([
        adminApi.getShifts({
          status: status || undefined,
          page,
          page_size: pageSize,
        }),
        adminApi.getPumps({ page: 1, page_size: 100 }),
        adminApi.getWorkers({ page: 1, page_size: 100 }),
      ]);
      setShifts(Array.isArray(shiftsRes) ? shiftsRes : shiftsRes?.items ?? []);
      setTotal(shiftsRes?.total ?? 0);
      setPumps(Array.isArray(pumpsRes) ? pumpsRes : pumpsRes?.items ?? []);
      setWorkers(Array.isArray(workersRes) ? workersRes : workersRes?.items ?? []);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load shifts."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, page]);

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
        description="Start, monitor, and close shifts at your pumps."
        actions={
          <Button
            onClick={() => setStartOpen(true)}
            disabled={pumps.length === 0 || workers.length === 0}
          >
            <Play className="h-4 w-4" /> Start shift
          </Button>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Select
          label="Status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="COMPLETED">Completed</option>
          <option value="RECONCILED">Reconciled</option>
          <option value="LOCKED">Locked</option>
        </Select>
      </div>

      <DataTable<Shift>
        data={shifts}
        loading={loading}
        rowKey={(s) => s.id}
        onRowClick={(s) => navigate(`/admin/shifts/${s.id}`)}
        emptyState={
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <Activity className="h-6 w-6 text-slate-400" />
            <span>No shifts found.</span>
          </div>
        }
        columns={[
          {
            key: "date",
            header: "Started",
            render: (s) => new Date(s.start_time).toLocaleString(),
          },
          { key: "pump", header: "Pump", render: (s) => pumpName(s.pump_id) },
          {
            key: "worker",
            header: "Worker",
            render: (s) => workerCode(s.worker_id),
          },
          {
            key: "status",
            header: "Status",
            render: (s) => (
              <Badge tone={statusBadgeTone(s.status)}>{s.status}</Badge>
            ),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (s) =>
              s.status === "ACTIVE" ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setCloseShift(s);
                  }}
                  className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-500"
                >
                  <StopCircle className="h-3 w-3" /> Close
                </button>
              ) : null,
          },
        ]}
      />

      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={setPage}
      />

      <StartShiftModal
        open={startOpen}
        pumps={pumps}
        workers={workers}
        onClose={() => setStartOpen(false)}
        onCreated={() => {
          setStartOpen(false);
          void loadAll();
        }}
      />
      <CloseShiftModal
        shift={closeShift}
        onClose={() => setCloseShift(null)}
        onClosed={() => {
          setCloseShift(null);
          void loadAll();
        }}
      />
    </div>
  );
}

function StartShiftModal({
  open,
  pumps,
  workers,
  onClose,
  onCreated,
}: {
  open: boolean;
  pumps: Pump[];
  workers: Worker[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [pumpId, setPumpId] = useState("");
  const [workerId, setWorkerId] = useState("");
  const [slot, setSlot] = useState("morning");
  const [nozzles, setNozzles] = useState<Nozzle[]>([]);
  const [openings, setOpenings] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!pumpId) {
      setNozzles([]);
      return;
    }
    (async () => {
      try {
        const p = await adminApi.getPump(pumpId);
        setNozzles(p.nozzles ?? []);
      } catch {
        setNozzles([]);
      }
    })();
  }, [pumpId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pumpId || !workerId) {
      toast.error("Pump and worker are required.");
      return;
    }
    setBusy(true);
    try {
      const shift = await shiftsApi.startShift({
        pump_id: pumpId,
        worker_id: workerId,
        start_time: new Date().toISOString(),
        slot,
      });
      // Record opening readings per nozzle if entered
      for (const n of nozzles) {
        const val = openings[n.id];
        if (val && val.trim() !== "") {
          await shiftsApi
            .saveMeterReadings(shift.id, {
              nozzle_id: n.id,
              closing_reading: Number(val),
            })
            .catch(() => {
              /* opening captured best-effort */
            });
        }
      }
      toast.success("Shift started.");
      onCreated();
    } catch (err) {
      toast.error(errMsg(err, "Failed to start shift."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Start shift"
      widthClass="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={busy || !pumpId || !workerId}
          >
            {busy ? "Starting…" : "Start"}
          </Button>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Pump"
            value={pumpId}
            onChange={(e) => setPumpId(e.target.value)}
            placeholder="Select pump…"
            options={pumps.map((p) => ({ value: p.id, label: p.name }))}
          />
          <Select
            label="Worker"
            value={workerId}
            onChange={(e) => setWorkerId(e.target.value)}
            placeholder="Select worker…"
            options={workers.map((w) => ({
              value: w.id,
              label: w.employee_code,
            }))}
          />
          <Select
            label="Slot"
            value={slot}
            onChange={(e) => setSlot(e.target.value)}
            options={[
              { value: "morning", label: "Morning" },
              { value: "afternoon", label: "Afternoon" },
              { value: "night", label: "Night" },
              { value: "full_day", label: "Full day" },
            ]}
          />
        </div>
        {nozzles.length > 0 && (
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-600 mb-2">
              Opening readings
            </div>
            <div className="space-y-2">
              {nozzles.map((n) => (
                <div key={n.id} className="flex items-center gap-3">
                  <span className="text-sm text-slate-700 w-28">
                    #{n.nozzle_number} — {n.fuel_type}
                  </span>
                  <Input
                    type="number"
                    step="0.01"
                    placeholder="0.00"
                    value={openings[n.id] ?? ""}
                    onChange={(e) =>
                      setOpenings((prev) => ({
                        ...prev,
                        [n.id]: e.target.value,
                      }))
                    }
                    className="flex-1"
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </form>
    </Modal>
  );
}

function CloseShiftModal({
  shift,
  onClose,
  onClosed,
}: {
  shift: Shift | null;
  onClose: () => void;
  onClosed: () => void;
}) {
  const [nozzles, setNozzles] = useState<Nozzle[]>([]);
  const [closings, setClosings] = useState<Record<string, string>>({});
  const [cashAmount, setCashAmount] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!shift) return;
    (async () => {
      try {
        const p = await adminApi.getPump(shift.pump_id);
        setNozzles(p.nozzles ?? []);
        setClosings({});
      } catch {
        setNozzles([]);
      }
    })();
  }, [shift]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!shift) return;
    setBusy(true);
    try {
      for (const n of nozzles) {
        const val = closings[n.id];
        if (val && val.trim() !== "") {
          await shiftsApi.saveMeterReadings(shift.id, {
            nozzle_id: n.id,
            closing_reading: Number(val),
          });
        }
      }
      if (cashAmount.trim()) {
        await shiftsApi.saveCashEntry({
          shift_id: shift.id,
          physical_cash: Number(cashAmount),
        });
      }
      await shiftsApi.closeShift(shift.id, {
        end_time: new Date().toISOString(),
        status: "COMPLETED",
      });
      toast.success("Shift closed.");
      onClosed();
    } catch (err) {
      toast.error(errMsg(err, "Failed to close shift."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={!!shift}
      onClose={onClose}
      title={shift ? `Close shift ${shift.id.slice(0, 8)}` : "Close shift"}
      widthClass="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={(e) => void onSubmit(e as unknown as FormEvent)}
            disabled={busy}
          >
            {busy ? "Closing…" : "Close shift"}
          </Button>
        </>
      }
    >
      {shift && (
        <form onSubmit={onSubmit} className="space-y-4">
          {nozzles.length > 0 && (
            <div>
              <div className="text-xs uppercase tracking-wide text-slate-600 mb-2">
                Closing readings
              </div>
              <div className="space-y-2">
                {nozzles.map((n) => (
                  <div key={n.id} className="flex items-center gap-3">
                    <span className="text-sm text-slate-700 w-28">
                      #{n.nozzle_number} — {n.fuel_type}
                    </span>
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      value={closings[n.id] ?? ""}
                      onChange={(e) =>
                        setClosings((prev) => ({
                          ...prev,
                          [n.id]: e.target.value,
                        }))
                      }
                      className="flex-1"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
          <Input
            label="Cash counted (₹)"
            type="number"
            min={0}
            step="0.01"
            value={cashAmount}
            onChange={(e) => setCashAmount(e.target.value)}
          />
        </form>
      )}
    </Modal>
  );
}
