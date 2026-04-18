import { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Mail, Shield, KeyRound } from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { Spinner } from "../../components/ui/Spinner";
import {
  changePasswordRequest,
  meRequest,
  type MeResponse,
} from "../../api/auth";

export default function ProviderSettingsPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const u = await meRequest();
        setMe(u);
      } catch {
        toast.error("Could not load your profile.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function changePw(e: FormEvent) {
    e.preventDefault();
    if (newPw !== confirmPw) {
      toast.error("New passwords do not match.");
      return;
    }
    if (newPw.length < 8) {
      toast.error("New password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      const res = await changePasswordRequest({
        old_password: oldPw,
        new_password: newPw,
      });
      toast.success(res.message);
      setOldPw("");
      setNewPw("");
      setConfirmPw("");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Could not change password.";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="mt-1 text-ink-400 text-sm">
          Manage your provider profile and account security.
        </p>
      </div>

      {loading ? (
        <Spinner label="Loading…" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <Shield className="h-4 w-4 text-brand-300" /> Profile
            </h3>
            {me ? (
              <dl className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <dt className="text-ink-500">Email</dt>
                  <dd className="font-medium flex items-center gap-2">
                    <Mail className="h-3.5 w-3.5 text-ink-400" />
                    {me.email}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-ink-500">Role</dt>
                  <dd>
                    <Badge tone="blue">{me.role}</Badge>
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-ink-500">Status</dt>
                  <dd>
                    <Badge tone={me.is_active ? "green" : "slate"}>
                      {me.is_active ? "active" : "inactive"}
                    </Badge>
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-ink-500">Last login</dt>
                  <dd className="text-ink-300">
                    {me.last_login
                      ? new Date(me.last_login).toLocaleString()
                      : "Never"}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="text-ink-500">Account created</dt>
                  <dd className="text-ink-300">
                    {new Date(me.created_at).toLocaleDateString()}
                  </dd>
                </div>
              </dl>
            ) : (
              <div className="text-sm text-ink-500">No profile loaded.</div>
            )}
          </Card>

          <Card>
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-amber-300" /> Change password
            </h3>
            <form onSubmit={changePw} className="space-y-4">
              <Input
                label="Current password"
                type="password"
                value={oldPw}
                onChange={(e) => setOldPw(e.target.value)}
                required
              />
              <Input
                label="New password"
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                required
              />
              <Input
                label="Confirm new password"
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                required
              />
              <Button
                type="submit"
                disabled={busy || !oldPw || !newPw || !confirmPw}
                className="w-full"
              >
                {busy ? "Updating…" : "Update password"}
              </Button>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
