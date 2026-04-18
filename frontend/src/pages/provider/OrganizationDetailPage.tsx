import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Lock, LockOpen } from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { providerApi, OrganizationDetail } from "../../api/provider";

const PLANS = ["BASIC", "PRO", "ENTERPRISE"];
const STATUSES = ["active", "trialing", "past_due", "cancelled"];

export default function OrganizationDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<OrganizationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [plan, setPlan] = useState("BASIC");
  const [status, setStatus] = useState("active");
  const [expires, setExpires] = useState("");
  const [price, setPrice] = useState(0);

  async function load() {
    if (!id) return;
    try {
      const d = await providerApi.organization(id);
      setData(d);
      setPlan(d.summary.subscription_plan);
      setStatus(d.summary.subscription_status);
      setExpires(
        d.summary.subscription_expires_at
          ? d.summary.subscription_expires_at.slice(0, 10)
          : "",
      );
      setPrice(d.summary.monthly_price_inr);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!id) return;
    setSaving(true);
    try {
      await providerApi.updateSubscription(id, {
        plan,
        status,
        expires_at: expires ? new Date(expires).toISOString() : null,
        monthly_price_inr: price,
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function toggleLock() {
    if (!id || !data) return;
    if (data.summary.is_locked) await providerApi.unlock(id);
    else await providerApi.lock(id);
    load();
  }

  if (!data) {
    return <div className="text-ink-400">{error ?? "Loading…"}</div>;
  }

  const s = data.summary;

  return (
    <div className="space-y-6">
      <Link
        to="/provider/organizations"
        className="inline-flex items-center gap-1.5 text-sm text-ink-400 hover:text-ink-200"
      >
        <ArrowLeft className="h-4 w-4" /> All organisations
      </Link>

      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold">{s.name}</h1>
          <div className="text-ink-400 text-sm">{s.owner_email}</div>
          <div className="mt-3 flex gap-2">
            <Badge tone="blue">{s.subscription_plan}</Badge>
            <Badge
              tone={s.subscription_status === "active" ? "green" : "amber"}
            >
              {s.subscription_status}
            </Badge>
            {s.is_locked ? (
              <Badge tone="red">Locked</Badge>
            ) : (
              <Badge tone="green">Open</Badge>
            )}
          </div>
        </div>
        <Button
          variant={s.is_locked ? "secondary" : "danger"}
          onClick={toggleLock}
        >
          {s.is_locked ? (
            <>
              <LockOpen className="h-4 w-4" /> Unlock tenant
            </>
          ) : (
            <>
              <Lock className="h-4 w-4" /> Lock tenant
            </>
          )}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-1">
          <h3 className="font-semibold mb-4">Subscription</h3>
          <form onSubmit={save} className="space-y-4">
            <div>
              <label className="block text-xs font-medium uppercase tracking-wide text-ink-400 mb-1.5">
                Plan
              </label>
              <select
                value={plan}
                onChange={(e) => setPlan(e.target.value)}
                className="w-full rounded-lg border border-ink-700 bg-ink-900/60 px-3 py-2.5 text-sm"
              >
                {PLANS.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium uppercase tracking-wide text-ink-400 mb-1.5">
                Status
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full rounded-lg border border-ink-700 bg-ink-900/60 px-3 py-2.5 text-sm"
              >
                {STATUSES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </div>
            <Input
              label="Expires at"
              type="date"
              value={expires}
              onChange={(e) => setExpires(e.target.value)}
            />
            <Input
              label="Monthly price (INR)"
              type="number"
              value={price}
              onChange={(e) => setPrice(Number(e.target.value) || 0)}
            />
            <Button type="submit" disabled={saving} className="w-full">
              {saving ? "Saving…" : "Save subscription"}
            </Button>
          </form>
        </Card>

        <Card className="lg:col-span-2">
          <h3 className="font-semibold mb-4">Users ({data.users.length})</h3>
          <div className="divide-y divide-ink-800">
            {data.users.map((u) => (
              <div
                key={u.id}
                className="py-2.5 flex items-center justify-between text-sm"
              >
                <div>
                  <div className="font-medium">{u.email}</div>
                  <div className="text-xs text-ink-500">
                    {u.role} · last login{" "}
                    {u.last_login
                      ? new Date(u.last_login).toLocaleString()
                      : "never"}
                  </div>
                </div>
                <Badge tone={u.is_active ? "green" : "slate"}>
                  {u.is_active ? "active" : "inactive"}
                </Badge>
              </div>
            ))}
            {data.users.length === 0 && (
              <div className="py-3 text-sm text-ink-500">No users.</div>
            )}
          </div>

          <h3 className="font-semibold mt-6 mb-4">
            Pumps ({data.pumps.length})
          </h3>
          <div className="divide-y divide-ink-800">
            {data.pumps.map((p) => (
              <div
                key={p.id}
                className="py-2.5 flex items-center justify-between text-sm"
              >
                <div>
                  <div className="font-medium">{p.name}</div>
                  <div className="text-xs text-ink-500 font-mono">
                    {p.code ?? "no code"}
                  </div>
                </div>
                <Badge tone={p.is_active ? "green" : "slate"}>
                  {p.is_active ? "active" : "inactive"}
                </Badge>
              </div>
            ))}
            {data.pumps.length === 0 && (
              <div className="py-3 text-sm text-ink-500">No pumps.</div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
