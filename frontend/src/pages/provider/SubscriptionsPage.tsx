import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { Badge, Card } from "../../components/ui";
import { PageHeader } from "../../components/ui/PageHeader";
import {
  providerApi,
  SubscriptionsResponse,
  SubscriptionGroup,
  TenantSummary,
} from "../../api/provider";

const TONE_BY_STATUS: Record<string, "green" | "amber" | "red" | "slate"> = {
  ACTIVE: "green",
  active: "green",
  TRIAL: "amber",
  trialing: "amber",
  EXPIRED: "red",
  past_due: "red",
  CANCELLED: "slate",
  cancelled: "slate",
};

function fmtINR(v: number): string {
  return `₹${v.toLocaleString("en-IN")}`;
}

function TenantCard({ t }: { t: TenantSummary }) {
  return (
    <Link
      to={`/provider/tenants/${t.tenant_id}`}
      className="block rounded-xl border border-slate-200 bg-white p-4 hover:border-indigo-400 hover:shadow-sm transition"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-semibold text-sm text-slate-900">{t.name}</div>
        <Badge tone="indigo">{t.subscription_plan}</Badge>
      </div>
      <div className="mt-2 text-xs text-slate-500">{t.owner_email}</div>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-slate-500">
          {t.subscription_expires_at
            ? `Renews ${new Date(t.subscription_expires_at).toLocaleDateString()}`
            : "No expiry"}
        </span>
        <span className="font-mono text-slate-900">
          {fmtINR(t.monthly_price_inr)}
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
          <span className="text-xs text-slate-500">{group.count}</span>
        </div>
        <span className="text-xs font-mono text-slate-500">
          {fmtINR(group.mrr_inr)}
        </span>
      </div>
      <div className="space-y-2 min-h-[6rem]">
        {group.organizations.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-4 text-center text-xs text-slate-400">
            No tenants
          </div>
        ) : (
          group.organizations.map((o) => <TenantCard key={o.tenant_id} t={o} />)
        )}
      </div>
    </div>
  );
}

export default function SubscriptionsPage() {
  const [data, setData] = useState<SubscriptionsResponse | null>(null);

  useEffect(() => {
    providerApi
      .getSubscriptions()
      .then(setData)
      .catch((e: Error) => toast.error(e?.message ?? "Failed to load"));
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
      <PageHeader
        title="Subscriptions"
        description="Kanban view of tenants by subscription status."
        actions={
          data && (
            <Card className="py-3 px-4">
              <div className="text-xs uppercase tracking-wider text-slate-500">
                Total MRR
              </div>
              <div className="text-2xl font-bold font-mono text-slate-900">
                {fmtINR(data.total_mrr_inr)}
              </div>
            </Card>
          )
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        {columns.map((g) => (
          <Column key={g.status} group={g} />
        ))}
      </div>
    </div>
  );
}
