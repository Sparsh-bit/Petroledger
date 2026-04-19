import { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Download } from "lucide-react";
import { Button, Card } from "../../components/ui";
import { Select } from "../../components/ui/Select";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, Shift } from "../../api/admin";
import { reportsApi } from "../../api/reports";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function ManagerReportsPage() {
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [shiftId, setShiftId] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const res = await adminApi.getShifts({ page: 1, page_size: 50 });
        if (!cancel) setShifts(res.items);
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancel = true;
    };
  }, []);

  async function onDownload(e: FormEvent) {
    e.preventDefault();
    if (!shiftId) {
      toast.error("Pick a shift.");
      return;
    }
    setBusy(true);
    try {
      await reportsApi.downloadShiftReport(shiftId);
      toast.success("Report downloaded.");
    } catch (err) {
      toast.error(errMsg(err, "Download failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Generate shift PDFs for your pump."
      />
      <Card>
        <form
          onSubmit={onDownload}
          className="flex items-end gap-3 flex-wrap"
        >
          <div className="flex-1 min-w-[240px]">
            <Select
              label="Shift"
              value={shiftId}
              onChange={(e) => setShiftId(e.target.value)}
              placeholder="Select shift…"
              options={shifts.map((s) => ({
                value: s.id,
                label: `${s.id.slice(0, 8)} — ${new Date(s.start_time).toLocaleString()}`,
              }))}
            />
          </div>
          <Button type="submit" disabled={busy || !shiftId}>
            <Download className="h-4 w-4" />
            {busy ? "Generating…" : "Download PDF"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
