import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import {
  ArrowLeft,
  Mail,
  Phone,
  Loader2,
  Check,
  X as XIcon,
  MessageSquare,
  UserPlus,
} from "lucide-react";
import { Button, Card } from "../../components/ui";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import {
  AccessRequest,
  AccessRequestStatus,
  accessRequestsApi,
} from "../../api/access-requests";

const STATUS_BADGE: Record<AccessRequestStatus, string> = {
  NEW: "bg-amber-50 text-amber-700 ring-1 ring-amber-200",
  CONTACTED: "bg-sky-50 text-sky-700 ring-1 ring-sky-200",
  APPROVED: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
  REJECTED: "bg-red-50 text-red-700 ring-1 ring-red-200",
};

const STATUSES: AccessRequestStatus[] = [
  "NEW",
  "CONTACTED",
  "APPROVED",
  "REJECTED",
];

export default function AccessRequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [req, setReq] = useState<AccessRequest | null>(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [savingNotes, setSavingNotes] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmApprove, setConfirmApprove] = useState(false);

  useEffect(() => {
    if (!id) return;
    accessRequestsApi
      .detail(id)
      .then((r) => {
        setReq(r);
        setNotes(r.provider_notes ?? "");
      })
      .catch((e) => setError(e?.message ?? "Failed to load"));
  }, [id]);

  async function updateStatus(status: AccessRequestStatus) {
    if (!id) return;
    setSaving(true);
    try {
      const updated = await accessRequestsApi.update(id, { status });
      setReq(updated);
      toast.success(`Marked as ${status.toLowerCase()}`);
    } catch (e: unknown) {
      toast.error(
        (e as { message?: string })?.message ?? "Could not update status",
      );
    } finally {
      setSaving(false);
    }
  }

  async function saveNotes() {
    if (!id || !req) return;
    if ((req.provider_notes ?? "") === notes) return;
    setSavingNotes(true);
    try {
      const updated = await accessRequestsApi.update(id, {
        provider_notes: notes,
      });
      setReq(updated);
      toast.success("Notes saved");
    } catch (e: unknown) {
      toast.error(
        (e as { message?: string })?.message ?? "Could not save notes",
      );
    } finally {
      setSavingNotes(false);
    }
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!req) {
    return <div className="text-slate-500 text-sm">Loading…</div>;
  }

  const status = req.status as AccessRequestStatus;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate("/provider/access-requests")}
          className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to requests
        </button>
        <span
          className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-mono uppercase tracking-wider ${STATUS_BADGE[status]}`}
        >
          {status}
        </span>
      </div>

      <Card>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              {req.full_name}
            </h1>
            <p className="mt-1 text-slate-500">{req.company}</p>
          </div>
          <div className="flex gap-2">
            <a
              href={`mailto:${req.email}`}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 hover:bg-slate-50"
            >
              <Mail className="h-4 w-4" /> Email
            </a>
            <a
              href={`tel:${req.phone}`}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 hover:bg-slate-50"
            >
              <Phone className="h-4 w-4" /> Call
            </a>
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <Field label="Email" value={req.email} />
          <Field label="Phone" value={req.phone} mono />
          <Field label="Pumps" value={req.pump_count_range} />
          <Field label="Location" value={`${req.city}, ${req.state}`} />
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wider text-slate-500">
              Submitted
            </dt>
            <dd className="mt-1 text-slate-900">
              {new Date(req.created_at).toLocaleString()}
            </dd>
          </div>
          {req.message && (
            <div className="sm:col-span-2">
              <dt className="text-xs uppercase tracking-wider text-slate-500">
                Message
              </dt>
              <dd className="mt-1 text-slate-900 whitespace-pre-wrap leading-relaxed">
                {req.message}
              </dd>
            </div>
          )}
        </dl>
      </Card>

      <Card>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
          Quick actions
        </h2>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={saving || status === "CONTACTED"}
            onClick={() => updateStatus("CONTACTED")}
          >
            <MessageSquare className="h-4 w-4" />
            Mark as Contacted
          </Button>
          <Button
            variant="primary"
            disabled={saving || status === "APPROVED"}
            onClick={() => setConfirmApprove(true)}
          >
            <Check className="h-4 w-4" />
            Approve
          </Button>
          <Button
            variant="danger"
            disabled={saving || status === "REJECTED"}
            onClick={() => updateStatus("REJECTED")}
          >
            <XIcon className="h-4 w-4" />
            Reject
          </Button>
        </div>

        <div className="mt-6">
          <label className="block text-xs uppercase tracking-wider text-slate-500 mb-2">
            Status
          </label>
          <select
            value={status}
            disabled={saving}
            onChange={(e) =>
              updateStatus(e.target.value as AccessRequestStatus)
            }
            className="w-48 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            Provider notes
          </h2>
          {savingNotes && (
            <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
          )}
        </div>
        <textarea
          rows={5}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={saveNotes}
          placeholder="Internal notes (autosaves on blur)…"
          className="mt-3 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
        />
        <div className="mt-3 flex justify-end">
          <Button
            variant="secondary"
            onClick={saveNotes}
            disabled={savingNotes}
          >
            Save notes
          </Button>
        </div>
      </Card>

      <ConfirmDialog
        open={confirmApprove}
        title="Approve and create tenant?"
        message="Approving marks this request APPROVED. Creating the tenant + owner login is still a manual step in the Tenants section."
        confirmLabel="Approve"
        onCancel={() => setConfirmApprove(false)}
        onConfirm={async () => {
          setConfirmApprove(false);
          await updateStatus("APPROVED");
          toast.custom(
            (t) => (
              <div
                className={`flex items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-md text-sm ${t.visible ? "animate-enter" : "animate-leave"}`}
              >
                <UserPlus className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                <span>
                  Approved. Next step:{" "}
                  <Link
                    to="/provider/tenants"
                    onClick={() => toast.dismiss(t.id)}
                    className="text-indigo-600 underline"
                  >
                    create the tenant manually
                  </Link>
                  .
                </span>
              </div>
            ),
            { duration: 6000 },
          );
        }}
      />
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
      <dt className="text-xs uppercase tracking-wider text-slate-500">
        {label}
      </dt>
      <dd
        className={`mt-1 text-slate-900 ${mono ? "font-mono" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}
