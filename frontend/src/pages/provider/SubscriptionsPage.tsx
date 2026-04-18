import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Badge } from "../../components/ui";
import {
  providerApi,
  SubscriptionsResponse,
  SubscriptionGroup,
  OrganizationSummary,
} from "../../api/provider";

const TONE_BY_STATUS: Record<string, "green" | "amber" | "red" | "slate"> = {
  ACTIVE: "green",
  TRIAL: "amber",
  EXPIRED: "red",
  CANCELLED: "slate",
};

function formatINR(v: number): string {
  return `₹${v.toLocaleString("en-IN")}`;
}

function OrgCard({ o }: { o: OrganizationSummary }) {
  return (
    <Link
      to={`/provider/organizations/${o.tenant_id}`}
      className="block rounded-xl border border-ink-800 bg-ink-950/40 p-4 hover:border-brand-500/50 hover:bg-ink-900/60 transition"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-semibold text-sm">{o.name}</div>
        <Badge tone="blue">{o.subscription_plan}</Badge>
      </div>
      <div className="mt-2 text-xs text-ink-400">{o.owner_email}</div>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-ink-400">
          {o.subscription_expires_at
            ? `Renews ${new Date(o.subscription_expires_at).toLocaleDateString()}`
            : "No expiry"}
        </span>
        <span className="font-mono text-ink-200">
          {formatINR(o.monthly_price_inr)}
        </span>
      </div>
    </Link>
  );
}

function Column({ group }: { group: SubscriptionGroup }) {
  const tone = TONE_BY_STATUS[group.status] ?? "slate";
  return (
    <div className="flex flex-col min-w-0">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Badge tone={tone}>{group.status}</Badge>
          <span className="text-xs text-ink-500">{group.count}</span>
        </div>
        <span className="text-xs font-mono text-ink-400">
          {formatINR(group.mrr_inr)}
        </span>
      </div>
      <div className="space-y-2 min-h-[6rem]">
        {group.organizations.length === 0 ? (
          <div className="rounded-xl border border-dashed border-ink-800 p-4 text-center text-xs text-ink-500">
            No organizations
          </div>
        ) : (
          group.organizations.map((o) => <OrgCard key={o.tenant_id} o={o} />)
        )}
      </div>
    </div>
  );
}

export default function SubscriptionsPage() {
  const [data, setData] = useState<SubscriptionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    providerApi
      .subscriptions()
      .then(setData)
      .catch((e: Error) => setError(e?.message ?? "Failed to load"));
  }, []);

  const columns: SubscriptionGroup[] =
    data?.groups ??
    (["ACTIVE", "TRIAL", "EXPIRED", "CANCELLED"].map((s) => ({
      status: s,
      count: 0,
      mrr_inr: 0,
      organizations: [],
    })) as SubscriptionGroup[]);

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">Subscriptions</h1>
          <p className="mt-1 text-ink-400 text-sm">
            Kanban view of tenants by subscription status.
          </p>
        </div>
        {data && (
          <Card className="py-3 px-4">
            <div className="text-xs uppercase tracking-wider text-ink-500">
              Total MRR
            </div>
            <div className="text-2xl font-bold font-mono">
              {formatINR(data.total_mrr_inr)}
            </div>
          </Card>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        {columns.map((g) => (
          <Column key={g.status} group={g} />
        ))}
      </div>
    </div>
  );
}
