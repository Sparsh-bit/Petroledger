import { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Mail, Shield, KeyRound, Server, Sliders } from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { PageHeader } from "../../components/ui/PageHeader";
import { Spinner } from "../../components/ui/Spinner";
import {
  changePasswordRequest,
  meRequest,
  type MeResponse,
} from "../../api/auth";
import { providerApi, ProviderSettings } from "../../api/provider";

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function ProviderSettingsPage() {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [settings, setSettings] = useState<ProviderSettings>({});
  const [loading, setLoading] = useState(true);
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const [u, s] = await Promise.all([
          meRequest(),
          providerApi.getProviderSettings(),
        ]);
        setMe(u);
        setSettings(s);
      } catch {
        toast.error("Could not load settings.");
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
    } catch (err) {
      toast.error(errMsg(err, "Could not change password."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Provider account + platform configuration."
      />

      {loading ? (
        <Spinner label="Loading…" />
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <h3 className="font-semibold mb-4 flex items-center gap-2 text-slate-900">
                <Shield className="h-4 w-4 text-indigo-500" /> Profile
              </h3>
              {me ? (
                <dl className="space-y-3 text-sm">
                  <Row label="Email">
                    <span className="flex items-center gap-2">
                      <Mail className="h-3.5 w-3.5 text-slate-400" />
                      {me.email}
                    </span>
                  </Row>
                  <Row label="Role">
                    <Badge tone="indigo">{me.role}</Badge>
                  </Row>
                  <Row label="Status">
                    <Badge tone={me.is_active ? "green" : "slate"}>
                      {me.is_active ? "active" : "inactive"}
                    </Badge>
                  </Row>
                  <Row label="Last login">
                    <span className="text-slate-600">
                      {me.last_login
                        ? new Date(me.last_login).toLocaleString()
                        : "Never"}
                    </span>
                  </Row>
                  <Row label="Account created">
                    <span className="text-slate-600">
                      {new Date(me.created_at).toLocaleDateString()}
                    </span>
                  </Row>
                </dl>
              ) : (
                <div className="text-sm text-slate-500">No profile loaded.</div>
              )}
            </Card>

            <Card>
              <h3 className="font-semibold mb-4 flex items-center gap-2 text-slate-900">
                <KeyRound className="h-4 w-4 text-amber-500" /> Change password
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

          <Card>
            <h3 className="font-semibold mb-4 flex items-center gap-2 text-slate-900">
              <Server className="h-4 w-4 text-slate-500" /> Platform configuration
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <Row label="SMTP configured">
                <Badge tone={settings.smtp_configured ? "green" : "slate"}>
                  {settings.smtp_configured ? "Yes" : "No"}
                </Badge>
              </Row>
              <Row label="Default plan">
                <span className="text-slate-900">
                  {settings.default_plan ?? "BASIC"}
                </span>
              </Row>
              <Row label="Rate limit threshold">
                <span className="text-slate-900">
                  {settings.rate_limit_threshold ?? "—"}
                </span>
              </Row>
              <Row label="Maintenance mode">
                <Badge tone={settings.maintenance_mode ? "red" : "green"}>
                  {settings.maintenance_mode ? "On" : "Off"}
                </Badge>
              </Row>
            </div>
            <div className="mt-4 text-xs text-slate-400 flex items-center gap-1.5">
              <Sliders className="h-3 w-3" /> Edit UI — backend endpoint pending.
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900">{children}</dd>
    </div>
  );
}
