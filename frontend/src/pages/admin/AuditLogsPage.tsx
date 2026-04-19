import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { ScrollText } from "lucide-react";
import { Button, Input } from "../../components/ui";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { DataTable, Pagination } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, AuditLogItem } from "../../api/admin";
import { useOrgStore } from "../../store/org";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function AuditLogsPage() {
  const { selectedOrgId } = useOrgStore();
  const [items, setItems] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [entityType, setEntityType] = useState("");
  const [action, setAction] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [detail, setDetail] = useState<AuditLogItem | null>(null);
  const [loading, setLoading] = useState(true);
  const pageSize = 50;

  async function load() {
    setLoading(true);
    try {
      const res = await adminApi.getAuditLogs({
        org_id: selectedOrgId ?? undefined,
        entity_type: entityType || undefined,
        action: action || undefined,
        start_date: startDate
          ? new Date(startDate).toISOString()
          : undefined,
        end_date: endDate ? new Date(endDate).toISOString() : undefined,
        page,
        page_size: pageSize,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load audit logs."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgId, entityType, action, startDate, endDate, page]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit logs"
        description="Immutable activity trail for this tenant."
      />

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Select
          label="Entity"
          value={entityType}
          onChange={(e) => {
            setEntityType(e.target.value);
            setPage(1);
          }}
          placeholder="All entities"
          options={[
            { value: "Pump", label: "Pump" },
            { value: "Worker", label: "Worker" },
            { value: "Shift", label: "Shift" },
            { value: "ReconciliationResult", label: "Reconciliation" },
            { value: "AnomalyFlag", label: "Anomaly" },
          ]}
        />
        <Input
          label="Action"
          placeholder="e.g. update"
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
        />
        <Input
          label="From"
          type="date"
          value={startDate}
          onChange={(e) => {
            setStartDate(e.target.value);
            setPage(1);
          }}
        />
        <Input
          label="To"
          type="date"
          value={endDate}
          onChange={(e) => {
            setEndDate(e.target.value);
            setPage(1);
          }}
        />
      </div>

      <DataTable<AuditLogItem>
        data={items}
        loading={loading}
        rowKey={(i) => i.id}
        onRowClick={(i) => setDetail(i)}
        emptyState={
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <ScrollText className="h-6 w-6 text-slate-400" />
            <span>No audit entries match the filters.</span>
          </div>
        }
        columns={[
          {
            key: "ts",
            header: "Timestamp",
            render: (i) => new Date(i.created_at).toLocaleString(),
          },
          {
            key: "user",
            header: "User",
            render: (i) =>
              i.user_id ? (
                <span className="font-mono text-xs">
                  {i.user_id.slice(0, 8)}
                </span>
              ) : (
                "system"
              ),
          },
          {
            key: "action",
            header: "Action",
            render: (i) => i.action,
          },
          {
            key: "entity",
            header: "Entity",
            render: (i) => (
              <div>
                <div>{i.entity_type}</div>
                <div className="text-xs font-mono text-slate-500">
                  {i.entity_id.slice(0, 8)}
                </div>
              </div>
            ),
          },
          {
            key: "ip",
            header: "IP",
            render: (i) => i.ip_address ?? "—",
          },
          {
            key: "more",
            header: "",
            align: "right",
            render: () => (
              <span className="text-xs text-indigo-600">View →</span>
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

      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        title="Audit log entry"
        widthClass="max-w-2xl"
        footer={
          <Button variant="ghost" onClick={() => setDetail(null)}>
            Close
          </Button>
        }
      >
        {detail && (
          <div className="space-y-4 text-sm">
            <dl className="grid grid-cols-2 gap-3">
              <Field label="Action" value={detail.action} />
              <Field label="Entity" value={detail.entity_type} />
              <Field
                label="Entity ID"
                value={detail.entity_id}
                mono
              />
              <Field
                label="User"
                value={detail.user_id ?? "system"}
                mono
              />
              <Field
                label="IP"
                value={detail.ip_address ?? "—"}
              />
              <Field
                label="Timestamp"
                value={new Date(detail.created_at).toLocaleString()}
              />
            </dl>
            <JsonBlock label="Before" value={detail.before_state ?? null} />
            <JsonBlock label="After" value={detail.after_state ?? null} />
          </div>
        )}
      </Modal>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd
        className={`mt-1 text-slate-900 ${mono ? "font-mono text-xs" : "font-medium"}`}
      >
        {value}
      </dd>
    </div>
  );
}

function JsonBlock({
  label,
  value,
}: {
  label: string;
  value: Record<string, unknown> | null;
}) {
  if (!value) return null;
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">
        {label}
      </div>
      <pre className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800 overflow-x-auto">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}
