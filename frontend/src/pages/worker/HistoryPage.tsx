import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { History } from "lucide-react";
import { Badge } from "../../components/ui";
import { DataTable, Pagination } from "../../components/ui/DataTable";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, Shift } from "../../api/admin";
import { statusBadgeTone } from "../admin/ShiftsPage";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function HistoryPage() {
  const navigate = useNavigate();
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const pageSize = 25;

  useEffect(() => {
    let cancel = false;
    (async () => {
      setLoading(true);
      try {
        const res = await adminApi.getShifts({ page, page_size: pageSize });
        if (!cancel) {
          setShifts(res.items);
          setTotal(res.total);
        }
      } catch (err) {
        if (!cancel) toast.error(errMsg(err, "Failed to load history."));
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, [page]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="History"
        description="Your past shifts."
      />

      <DataTable<Shift>
        data={shifts}
        loading={loading}
        rowKey={(s) => s.id}
        onRowClick={(s) => navigate(`/admin/shifts/${s.id}`)}
        emptyState={
          <div className="flex flex-col items-center gap-2 text-slate-500">
            <History className="h-6 w-6 text-slate-400" />
            <span>No past shifts yet.</span>
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
            render: (s) => (
              <span className="font-mono text-xs">
                {s.pump_id.slice(0, 8)}
              </span>
            ),
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
