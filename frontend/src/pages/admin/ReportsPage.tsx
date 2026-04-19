import { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Download, FileSpreadsheet, FileText } from "lucide-react";
import { Button, Card, Input } from "../../components/ui";
import { Select } from "../../components/ui/Select";
import { PageHeader } from "../../components/ui/PageHeader";
import { adminApi, Shift } from "../../api/admin";
import { reportsApi } from "../../api/reports";
import { useOrgStore } from "../../store/org";

type Tab = "shift" | "daily";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function ReportsPage() {
  const { selectedOrgId, orgs } = useOrgStore();
  const [tab, setTab] = useState<Tab>("shift");
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [shiftId, setShiftId] = useState("");
  const [reportDate, setReportDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [siteId, setSiteId] = useState(selectedOrgId ?? "");
  const [format, setFormat] = useState<"pdf" | "excel">("pdf");
  const [busyShift, setBusyShift] = useState(false);
  const [busyDaily, setBusyDaily] = useState(false);

  useEffect(() => {
    if (selectedOrgId) setSiteId(selectedOrgId);
  }, [selectedOrgId]);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const res = await adminApi.getShifts({
          org_id: selectedOrgId ?? undefined,
          page: 1,
          page_size: 50,
        });
        if (!cancel) setShifts(res.items);
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancel = true;
    };
  }, [selectedOrgId]);

  async function onShiftDownload(e: FormEvent) {
    e.preventDefault();
    if (!shiftId) {
      toast.error("Pick a shift.");
      return;
    }
    setBusyShift(true);
    try {
      await reportsApi.downloadShiftReport(shiftId);
      toast.success("Shift report downloaded.");
    } catch (err) {
      toast.error(errMsg(err, "Download failed."));
    } finally {
      setBusyShift(false);
    }
  }

  async function onDailyDownload(e: FormEvent) {
    e.preventDefault();
    if (!siteId) {
      toast.error("Pick an organisation.");
      return;
    }
    setBusyDaily(true);
    try {
      await reportsApi.downloadDailyReport({
        site_id: siteId,
        report_date: reportDate,
        format,
      });
      toast.success("Daily report downloaded.");
    } catch (err) {
      toast.error(errMsg(err, "Download failed."));
    } finally {
      setBusyDaily(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Generate shift PDFs and daily consolidation reports."
      />

      <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 w-fit">
        {(
          [
            ["shift", "Shift reports", FileText],
            ["daily", "Daily reports", FileSpreadsheet],
          ] as const
        ).map(([v, label, Icon]) => (
          <button
            key={v}
            type="button"
            onClick={() => setTab(v)}
            className={`inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md transition ${
              tab === v
                ? "bg-indigo-600 text-white"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {tab === "shift" ? (
        <Card>
          <h3 className="font-semibold text-slate-900 mb-4">Shift report</h3>
          <form
            onSubmit={onShiftDownload}
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
            <Button type="submit" disabled={busyShift || !shiftId}>
              <Download className="h-4 w-4" />
              {busyShift ? "Generating…" : "Download PDF"}
            </Button>
          </form>
        </Card>
      ) : (
        <Card>
          <h3 className="font-semibold text-slate-900 mb-4">Daily report</h3>
          <form
            onSubmit={onDailyDownload}
            className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end"
          >
            <Select
              label="Organisation"
              value={siteId}
              onChange={(e) => setSiteId(e.target.value)}
              placeholder="Select org…"
              options={orgs.map((o) => ({ value: o.id, label: o.name }))}
            />
            <Input
              label="Date"
              type="date"
              value={reportDate}
              onChange={(e) => setReportDate(e.target.value)}
            />
            <Select
              label="Format"
              value={format}
              onChange={(e) => setFormat(e.target.value as "pdf" | "excel")}
              options={[
                { value: "pdf", label: "PDF" },
                { value: "excel", label: "Excel" },
              ]}
            />
            <Button
              type="submit"
              disabled={busyDaily || !siteId || !reportDate}
            >
              <Download className="h-4 w-4" />
              {busyDaily ? "Generating…" : "Download"}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
