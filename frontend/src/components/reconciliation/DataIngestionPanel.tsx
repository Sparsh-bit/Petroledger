import { useState, useRef, useEffect } from "react";
import toast from "react-hot-toast";
import { Upload, FileText, CheckCircle2, AlertTriangle, RefreshCw } from "lucide-react";
import { Button, Card, Badge } from "../ui";
import { dataIngestionApi, IngestionKind, JobStatusResponse } from "../../api/dataIngestion";
import { errMsg } from "../../lib/errMsg";

export function DataIngestionPanel({ shiftId, pumpId, onComplete }: { shiftId: string; pumpId: string; onComplete?: () => void }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <IngestionCard title="UPI Transactions" kind="upi-csv" shiftId={shiftId} description="Upload phonepe/bharatpe/paytm settlement CSV." onComplete={onComplete} />
      <IngestionCard title="POS Settlements" kind="pos-slip" shiftId={shiftId} description="Upload POS settlement batch CSV." onComplete={onComplete} />
      <IngestionCard title="Pump Logs" kind="pump-logs" shiftId={shiftId} pumpId={pumpId} description="Upload automated dispenser logs." onComplete={onComplete} />
    </div>
  );
}

function IngestionCard({
  title,
  kind,
  shiftId,
  pumpId,
  description,
  onComplete
}: {
  title: string;
  kind: IngestionKind;
  shiftId: string;
  pumpId?: string;
  description: string;
  onComplete?: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatusResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Poll status when jobId exists and is not final
  useEffect(() => {
    if (!jobId) return;
    const isFinal = status?.status === "COMPLETED" || status?.status === "FAILED";
    if (isFinal) {
      if (status?.status === "COMPLETED") {
         onComplete?.();
      }
      return;
    }

    const interval = setInterval(() => {
      dataIngestionApi.getIngestionStatus(jobId)
        .then(res => setStatus(res))
        .catch(console.error);
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId, status?.status, onComplete]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setStatus(null);
    try {
      const res = await dataIngestionApi.uploadFile(kind, file, { shift_id: shiftId, pump_id: pumpId });
      setJobId(res.job_id);
      toast.success("Upload started!");
    } catch (err) {
      toast.error(errMsg(err, "Failed to upload file."));
      setJobId(null);
    } finally {
      setUploading(false);
    }
  }

  async function handleConfirm() {
    if (!jobId) return;
    setUploading(true);
    try {
      await dataIngestionApi.confirmIngestion(jobId);
      toast.success("Data committed successfully.");
      setJobId(null);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      onComplete?.();
    } catch (err) {
      toast.error(errMsg(err, "Failed to commit data."));
    } finally {
      setUploading(false);
    }
  }

  return (
    <Card>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="font-semibold text-slate-900">{title}</h3>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
        <FileText className="h-5 w-5 text-indigo-400" />
      </div>

      {!jobId && (
        <div className="mt-4 space-y-3">
          <input
            type="file"
            ref={fileInputRef}
            className="block w-full text-sm text-slate-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-md file:border-0
              file:text-sm file:font-semibold
              file:bg-indigo-50 file:text-indigo-700
              hover:file:bg-indigo-100"
            accept=".csv,.txt"
            onChange={e => setFile(e.target.files?.[0] ?? null)}
          />
          <Button onClick={handleUpload} disabled={!file || uploading} className="w-full">
            <Upload className="h-4 w-4 mr-2" />
            {uploading ? "Uploading..." : "Upload File"}
          </Button>
        </div>
      )}

      {jobId && status && (
        <div className="mt-4 p-3 rounded-lg bg-slate-50 border border-slate-100 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">Status</span>
            <Badge tone={status.status === "COMPLETED" ? "green" : status.status === "FAILED" ? "red" : "blue"}>
              {status.status}
            </Badge>
          </div>
          
          {status.status === "PROCESSING" && (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <RefreshCw className="h-4 w-4 animate-spin" /> Processing file...
            </div>
          )}

          {status.status === "FAILED" && (
            <div className="flex items-start gap-2 text-sm text-red-600">
              <AlertTriangle className="h-4 w-4 mt-0.5" />
              <span>{status.error ?? "Processing failed"}</span>
            </div>
          )}

          {status.status === "COMPLETED" && status.result && (
            <div className="space-y-3">
              <div className="flex items-start gap-2 text-sm text-emerald-600">
                <CheckCircle2 className="h-4 w-4 mt-0.5" />
                <span>Found {status.result.valid_rows} valid records out of {status.result.total_rows}.</span>
              </div>
              <Button onClick={handleConfirm} disabled={uploading} className="w-full" variant="primary">
                {uploading ? "Committing..." : "Commit Data to DB"}
              </Button>
              <Button onClick={() => {
                setJobId(null);
                setFile(null);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }} variant="secondary" className="w-full">
                Cancel / Upload Another
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
