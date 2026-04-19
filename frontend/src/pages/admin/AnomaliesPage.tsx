import { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { AlertTriangle } from "lucide-react";
import { Badge, Button } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { DataTable, Pagination } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, AnomalyFlag } from "../../api/admin";
import { useOrgStore } from "../../store/org";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

function sevTone(sev: string): "red" | "amber" | "slate" | "blue" {
  const s = sev.toUpperCase();
  if (s === "CRITICAL" || s === "HIGH") return "red";
  if (s === "MEDIUM") return "amber";
  if (s === "LOW") return "blue";
  return "slate";
}

export default function AnomaliesPage() {
  const { selectedOrgId } = useOrgStore();
  const [items, setItems] = useState<AnomalyFlag[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState("");
  const [resolved, setResolved] = useState("unresolved");
  const [detail, setDetail] = useState<AnomalyFlag | null>(null);
  const [resolutionNote, setResolutionNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const pageSize = 25;

  async function load() {
    if (!selectedOrgId) {
      setItems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const res = await adminApi.getAnomalies({
        site_id: selectedOrgId,
        severity: severity || undefined,
        is_resolved:
          resolved === "all" ? undefined : resolved === "resolved",
        page,
        page_size: pageSize,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load anomalies."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgId, severity, resolved, page]);

  async function onResolve(e: FormEvent) {
    e.preventDefault();
    if (!detail) return;
    if (!resolutionNote.trim()) {
      toast.error("Resolution note is required.");
      return;
    }
    setBusy(true);
    try {
      await adminApi.resolveAnomaly(detail.id, resolutionNote.trim());
      toast.success("Anomaly resolved.");
      setDetail(null);
      setResolutionNote("");
      void load();
    } catch (err) {
      toast.error(errMsg(err, "Failed to resolve."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Anomalies"
        description="Flagged irregularities from reconciliation and ML detection."
      />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Select
          label="Severity"
          value={severity}
          onChange={(e) => {
            setSeverity(e.target.value);
            setPage(1);
          }}
          placeholder="All severities"
          options={[
            { value: "LOW", label: "Low" },
            { value: "MEDIUM", label: "Medium" },
            { value: "HIGH", label: "High" },
            { value: "CRITICAL", label: "Critical" },
          ]}
        />
        <Select
          label="Status"
          value={resolved}
          onChange={(e) => {
            setResolved(e.target.value);
            setPage(1);
          }}
          options={[
            { value: "unresolved", label: "Unresolved only" },
            { value: "resolved", label: "Resolved" },
            { value: "all", label: "All" },
          ]}
        />
      </div>

      {!selectedOrgId ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          Pick an organisation in the top bar to view anomalies.
        </div>
      ) : (
        <>
          <DataTable<AnomalyFlag>
            data={items}
            loading={loading}
            rowKey={(a) => a.id}
            onRowClick={(a) => setDetail(a)}
            emptyState={
              <div className="flex flex-col items-center gap-2 text-slate-500">
                <AlertTriangle className="h-6 w-6 text-slate-400" />
                <span>No anomalies. System is quiet.</span>
              </div>
            }
            columns={[
              {
                key: "date",
                header: "Date",
                render: (a) => new Date(a.created_at).toLocaleString(),
              },
              {
                key: "severity",
                header: "Severity",
                render: (a) => (
                  <Badge tone={sevTone(a.severity)}>{a.severity}</Badge>
                ),
              },
              {
                key: "type",
                header: "Type",
                render: (a) => a.flag_type,
              },
              {
                key: "description",
                header: "Description",
                render: (a) => (
                  <span className="line-clamp-1">{a.description}</span>
                ),
              },
              {
                key: "status",
                header: "Status",
                render: (a) => (
                  <Badge tone={a.is_resolved ? "green" : "amber"}>
                    {a.is_resolved ? "Resolved" : "Open"}
                  </Badge>
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
        </>
      )}

      <Modal
        open={!!detail}
        onClose={() => {
          setDetail(null);
          setResolutionNote("");
        }}
        title="Anomaly detail"
        widthClass="max-w-xl"
        footer={
          detail && !detail.is_resolved ? (
            <>
              <Button
                variant="ghost"
                onClick={() => {
                  setDetail(null);
                  setResolutionNote("");
                }}
                disabled={busy}
              >
                Close
              </Button>
              <Button
                onClick={(e) => void onResolve(e as unknown as FormEvent)}
                disabled={busy || !resolutionNote.trim()}
              >
                {busy ? "Resolving…" : "Mark resolved"}
              </Button>
            </>
          ) : (
            <Button
              variant="ghost"
              onClick={() => {
                setDetail(null);
                setResolutionNote("");
              }}
            >
              Close
            </Button>
          )
        }
      >
        {detail && (
          <div className="space-y-4 text-sm">
            <dl className="grid grid-cols-2 gap-3">
              <Field label="Type" value={detail.flag_type} />
              <Field label="Severity" value={detail.severity} />
              <Field
                label="Status"
                value={detail.is_resolved ? "Resolved" : "Open"}
              />
              <Field
                label="Created"
                value={new Date(detail.created_at).toLocaleString()}
              />
              {detail.amount !== null && detail.amount !== undefined && (
                <Field
                  label="Amount"
                  value={`₹${Number(detail.amount).toLocaleString("en-IN")}`}
                />
              )}
              {detail.shift_id && (
                <Field label="Shift" value={detail.shift_id.slice(0, 8)} />
              )}
            </dl>
            <div>
              <div className="text-xs uppercase tracking-wide text-slate-500">
                Description
              </div>
              <p className="mt-1 text-slate-900">{detail.description}</p>
            </div>
            {detail.resolution_note && (
              <div>
                <div className="text-xs uppercase tracking-wide text-slate-500">
                  Resolution
                </div>
                <p className="mt-1 text-slate-900 whitespace-pre-wrap">
                  {detail.resolution_note}
                </p>
              </div>
            )}
            {!detail.is_resolved && (
              <div className="space-y-1.5">
                <label className="block text-xs font-medium uppercase tracking-wide text-slate-600">
                  Resolution note
                </label>
                <textarea
                  rows={4}
                  value={resolutionNote}
                  onChange={(e) => setResolutionNote(e.target.value)}
                  placeholder="Explain how this was resolved…"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
                />
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 text-slate-900 font-medium">{value}</dd>
    </div>
  );
}
