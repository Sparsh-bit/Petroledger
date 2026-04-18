import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Lock, LockOpen, Search } from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { providerApi, OrganizationSummary } from "../../api/provider";

export default function OrganizationsPage() {
  const [orgs, setOrgs] = useState<OrganizationSummary[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setOrgs(await providerApi.organizations());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return orgs;
    return orgs.filter(
      (o) =>
        o.name.toLowerCase().includes(term) ||
        o.owner_email.toLowerCase().includes(term),
    );
  }, [orgs, q]);

  async function toggleLock(o: OrganizationSummary) {
    if (o.is_locked) await providerApi.unlock(o.tenant_id);
    else await providerApi.lock(o.tenant_id);
    load();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Organizations</h1>
          <p className="mt-1 text-ink-400 text-sm">
            Manage every tenant on the platform.
          </p>
        </div>
        <div className="w-72">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-500" />
            <Input
              className="pl-9"
              placeholder="Search name or email…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      <Card className="p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-ink-900/80 text-xs uppercase text-ink-400">
              <tr>
                <th className="text-left px-5 py-3">Name</th>
                <th className="text-left px-5 py-3">Plan</th>
                <th className="text-left px-5 py-3">Status</th>
                <th className="text-left px-5 py-3">Pumps</th>
                <th className="text-left px-5 py-3">Users</th>
                <th className="text-left px-5 py-3">Locked</th>
                <th className="text-right px-5 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-ink-500">
                    Loading…
                  </td>
                </tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-ink-500">
                    No organisations match.
                  </td>
                </tr>
              )}
              {filtered.map((o) => (
                <tr key={o.tenant_id} className="border-t border-ink-800">
                  <td className="px-5 py-3">
                    <Link
                      to={`/provider/organizations/${o.tenant_id}`}
                      className="font-medium hover:text-brand-300"
                    >
                      {o.name}
                    </Link>
                    <div className="text-xs text-ink-500">{o.owner_email}</div>
                  </td>
                  <td className="px-5 py-3">
                    <Badge tone="blue">{o.subscription_plan}</Badge>
                  </td>
                  <td className="px-5 py-3">
                    <Badge
                      tone={
                        o.subscription_status === "active"
                          ? "green"
                          : o.subscription_status === "past_due"
                          ? "amber"
                          : "slate"
                      }
                    >
                      {o.subscription_status}
                    </Badge>
                  </td>
                  <td className="px-5 py-3 text-ink-300">{o.pump_count}</td>
                  <td className="px-5 py-3 text-ink-300">{o.user_count}</td>
                  <td className="px-5 py-3">
                    {o.is_locked ? (
                      <Badge tone="red">Locked</Badge>
                    ) : (
                      <Badge tone="green">Open</Badge>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right whitespace-nowrap">
                    <Link
                      to={`/provider/organizations/${o.tenant_id}`}
                      className="text-xs text-ink-300 hover:text-ink-50 mr-3"
                    >
                      View
                    </Link>
                    <Button
                      variant={o.is_locked ? "secondary" : "danger"}
                      onClick={() => toggleLock(o)}
                      className="py-1.5 px-3 text-xs"
                    >
                      {o.is_locked ? (
                        <>
                          <LockOpen className="h-3.5 w-3.5" /> Unlock
                        </>
                      ) : (
                        <>
                          <Lock className="h-3.5 w-3.5" /> Lock
                        </>
                      )}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
