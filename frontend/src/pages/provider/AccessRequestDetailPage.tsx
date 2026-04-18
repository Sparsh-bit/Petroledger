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
import { Card, Button } from "../../components/ui";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import {
  AccessRequest,
  AccessRequestStatus,
  accessRequestsApi,
} from "../../api/access-requests";

const STATUS_BADGE: Record<AccessRequestStatus, string> = {
  NEW: "bg-amber-400/15 text-amber-300 ring-1 ring-amber-400/30",
  CONTACTED: "bg-sky-400/15 text-sky-300 ring-1 ring-sky-400/30",
  APPROVED: "bg-emerald-400/15 text-emerald-300 ring-1 ring-emerald-400/30",
  REJECTED: "bg-red-400/15 text-red-300 ring-1 ring-red-400/30",
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
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
        {error}
      </div>
    );
  }

  if (!req) {
    return <div className="text-ink-400 text-sm">Loading…</div>;
  }

  const status = req.status as AccessRequestStatus;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate("/provider/access-requests")}
          className="inline-flex items-center gap-2 text-sm text-ink-400 hover:text-white"
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
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">{req.full_name}</h1>
            <p className="mt-1 text-ink-400">{req.company}</p>
          </div>
          <div className="flex gap-2">
            <a
              href={`mailto:${req.email}`}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-ink-700 bg-ink-900 text-sm hover:bg-ink-800"
            >
              <Mail className="h-4 w-4" /> Email
            </a>
            <a
              href={`tel:${req.phone}`}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-ink-700 bg-ink-900 text-sm hover:bg-ink-800"
            >
              <Phone className="h-4 w-4" /> Call
            </a>
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wider text-ink-500">Email</dt>
            <dd className="mt-1 text-ink-100">{req.email}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-ink-500">Phone</dt>
            <dd className="mt-1 text-ink-100 font-mono">{req.phone}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-ink-500">Pumps</dt>
            <dd className="mt-1 text-ink-100">{req.pump_count_range}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-ink-500">Location</dt>
            <dd className="mt-1 text-ink-100">
              {req.city}, {req.state}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wider text-ink-500">Submitted</dt>
            <dd className="mt-1 text-ink-100">
              {new Date(req.created_at).toLocaleString()}
            </dd>
          </div>
          {req.message && (
            <div className="sm:col-span-2">
              <dt className="text-xs uppercase tracking-wider text-ink-500">
                Message
              </dt>
              <dd className="mt-1 text-ink-100 whitespace-pre-wrap leading-relaxed">
                {req.message}
              </dd>
            </div>
          )}
        </dl>
      </Card>

      <Card>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-400">
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
          <label className="block text-xs uppercase tracking-wider text-ink-400 mb-2">
            Status
          </label>
          <select
            value={status}
            disabled={saving}
            onChange={(e) =>
              updateStatus(e.target.value as AccessRequestStatus)
            }
            className="w-48 rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s} className="bg-ink-900">
                {s}
              </option>
            ))}
          </select>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-400">
            Provider notes
          </h2>
          {savingNotes && (
            <Loader2 className="h-4 w-4 animate-spin text-ink-500" />
          )}
        </div>
        <textarea
          rows={5}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={saveNotes}
          placeholder="Internal notes (autosaves on blur)…"
          className="mt-3 w-full rounded-lg border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-ink-100 outline-none focus:border-amber-400/60"
        />
        <div className="mt-3 flex justify-end">
          <Button variant="secondary" onClick={saveNotes} disabled={savingNotes}>
            Save notes
          </Button>
        </div>
      </Card>

      <ConfirmDialog
        open={confirmApprove}
        title="Approve and create tenant?"
        message={
          "Approving marks this request APPROVED. Creating the tenant + owner login is still a manual step in the Organizations section. Continue?"
        }
        confirmLabel="Approve"
        onCancel={() => setConfirmApprove(false)}
        onConfirm={async () => {
          setConfirmApprove(false);
          await updateStatus("APPROVED");
          toast(
            (t) => (
              <span className="text-sm">
                Next step:{" "}
                <Link
                  to="/provider/organizations"
                  onClick={() => toast.dismiss(t.id)}
                  className="text-amber-300 underline"
                >
                  create the tenant manually
                </Link>
                .
              </span>
            ),
            { icon: <UserPlus className="h-4 w-4 text-emerald-300" /> },
          );
        }}
      />
    </div>
  );
}
