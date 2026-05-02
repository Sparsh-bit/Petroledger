import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import {
  ArrowLeft,
  Lock,
  LockOpen,
  Building2,
  CreditCard,
  AlertOctagon,
  Trash2,
  Zap,
  Wallet,
  LayoutDashboard,
  Save,
  Check,
} from "lucide-react";
import { Badge, Button, Card, Input } from "../../components/ui";
import { ConfirmDialog } from "../../components/ui/ConfirmDialog";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { PageHeader } from "../../components/ui/PageHeader";
import { SkeletonCard, SkeletonList } from "../../components/ui/Skeleton";
import {
  providerApi,
  TenantDetail,
  TenantFeatureItem,
  PaymentConfigResponse,
} from "../../api/provider";

// ── Types ──────────────────────────────────────────────────────────────────

type Tab = "overview" | "pumps" | "subscription" | "features" | "payments";

const PLANS = [
  {
    value: "BASIC",
    label: "BASIC",
    desc: "Single pump, essential operations",
    orgs: "1 organisation",
  },
  {
    value: "PRO",
    label: "PRO",
    desc: "Small chains — fleet, inventory & analytics",
    orgs: "Up to 5 organisations",
  },
  {
    value: "ENTERPRISE",
    label: "ENTERPRISE",
    desc: "Unlimited orgs, API access & SMS alerts",
    orgs: "Unlimited organisations",
  },
];

const STATUSES = ["active", "trialing", "past_due", "cancelled"];

const MODULE_LABELS: Record<string, string> = {
  core: "Core Features",
  analytics: "Analytics & Reporting",
  fleet: "Fleet Management",
  inventory: "Inventory Management",
  compliance: "Compliance & Reconciliation",
  operations: "Operations",
  advanced: "Advanced & Integrations",
};

const GATEWAYS = [
  { value: "razorpay", label: "Razorpay" },
  { value: "paytm", label: "Paytm" },
];

// ── Helpers ────────────────────────────────────────────────────────────────

function errMsg(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

// ── Tab button ─────────────────────────────────────────────────────────────

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
        active
          ? "bg-white shadow-sm text-slate-900"
          : "text-slate-500 hover:text-slate-700"
      }`}
    >
      {children}
    </button>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(true);

  // subscription form
  const [plan, setPlan] = useState("BASIC");
  const [subStatus, setSubStatus] = useState("active");
  const [expires, setExpires] = useState("");
  const [price, setPrice] = useState(0);
  const [saving, setSaving] = useState(false);

  // lock/delete
  const [pendingLock, setPendingLock] = useState(false);
  const [lockBusy, setLockBusy] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);

  // features
  const [features, setFeatures] = useState<TenantFeatureItem[]>([]);
  const [featuresLoading, setFeaturesLoading] = useState(false);

  // payment config
  const [payConfig, setPayConfig] = useState<PaymentConfigResponse | null>(null);
  const [payLoading, setPayLoading] = useState(false);
  const [gateway, setGateway] = useState("razorpay");
  const [keyId, setKeyId] = useState("");
  const [keySecret, setKeySecret] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const d = await providerApi.getTenant(id);
      setData(d);
      setPlan(d.summary.subscription_plan);
      setSubStatus(d.summary.subscription_status);
      setExpires(
        d.summary.subscription_expires_at
          ? d.summary.subscription_expires_at.slice(0, 10)
          : "",
      );
      setPrice(d.summary.monthly_price_inr);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load tenant."));
    } finally {
      setLoading(false);
    }
  }, [id]);

  const loadFeatures = useCallback(async () => {
    if (!id) return;
    setFeaturesLoading(true);
    try {
      setFeatures(await providerApi.getTenantFeatures(id));
    } catch (err) {
      toast.error(errMsg(err, "Failed to load features."));
    } finally {
      setFeaturesLoading(false);
    }
  }, [id]);

  const loadPayConfig = useCallback(async () => {
    if (!id) return;
    setPayLoading(true);
    try {
      const cfg = await providerApi.getPaymentConfig(id);
      setPayConfig(cfg);
      if (cfg.gateway) setGateway(cfg.gateway);
    } catch (err) {
      toast.error(errMsg(err, "Failed to load payment config."));
    } finally {
      setPayLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (tab === "features" && features.length === 0) void loadFeatures();
    if (tab === "payments" && payConfig === null) void loadPayConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function saveSubscription(e: FormEvent) {
    e.preventDefault();
    if (!id) return;
    setSaving(true);
    try {
      await providerApi.updateSubscription(id, {
        plan,
        status: subStatus,
        expires_at: expires ? new Date(expires).toISOString() : null,
        monthly_price_inr: price,
      });
      toast.success("Subscription updated.");
      await load();
    } catch (err) {
      toast.error(errMsg(err, "Failed to update subscription."));
    } finally {
      setSaving(false);
    }
  }

  async function confirmLockToggle() {
    if (!id || !data) return;
    setLockBusy(true);
    try {
      if (data.summary.is_locked) {
        await providerApi.unlockTenant(id);
        toast.success("Tenant unlocked.");
      } else {
        await providerApi.lockTenant(id);
        toast.success("Tenant locked.");
      }
      setPendingLock(false);
      void load();
    } catch (err) {
      toast.error(errMsg(err, "Failed to toggle lock."));
    } finally {
      setLockBusy(false);
    }
  }

  async function toggleFeature(f: TenantFeatureItem) {
    if (!id) return;
    setFeaturesLoading(true);
    try {
      await providerApi.setFeatureOverride(id, f.id, !f.effective, "Toggled by provider");
      toast.success(`${f.name} ${!f.effective ? "enabled" : "disabled"}`);
      void loadFeatures();
    } catch (err) {
      toast.error(errMsg(err, "Failed to update feature."));
      setFeaturesLoading(false);
    }
  }

  async function resetFeature(f: TenantFeatureItem) {
    if (!id) return;
    setFeaturesLoading(true);
    try {
      await providerApi.clearFeatureOverride(id, f.id);
      toast.success(`${f.name} reverted to plan default`);
      void loadFeatures();
    } catch (err) {
      toast.error(errMsg(err, "Failed to reset feature."));
      setFeaturesLoading(false);
    }
  }

  async function savePaymentConfig(e: FormEvent) {
    e.preventDefault();
    if (!id) return;
    if (!keyId || !keySecret) {
      toast.error("Key ID and Key Secret are required.");
      return;
    }
    setPayLoading(true);
    try {
      await providerApi.savePaymentConfig(id, {
        gateway,
        key_id: keyId,
        key_secret: keySecret,
        webhook_secret: webhookSecret || undefined,
      });
      toast.success("Payment credentials saved.");
      setKeyId("");
      setKeySecret("");
      setWebhookSecret("");
      void loadPayConfig();
    } catch (err) {
      toast.error(errMsg(err, "Failed to save payment config."));
    } finally {
      setPayLoading(false);
    }
  }

  async function removePaymentConfig() {
    if (!id || !confirm("Remove payment configuration? This cannot be undone.")) return;
    setPayLoading(true);
    try {
      await providerApi.deletePaymentConfig(id);
      toast.success("Payment configuration removed.");
      setPayConfig(null);
    } catch (err) {
      toast.error(errMsg(err, "Failed to remove payment config."));
    } finally {
      setPayLoading(false);
    }
  }

  async function togglePayments() {
    if (!id) return;
    setPayLoading(true);
    try {
      const updated = await providerApi.togglePaymentConfig(id);
      setPayConfig(updated);
      toast.success(`Payments ${updated.is_enabled ? "enabled" : "disabled"}.`);
    } catch (err) {
      toast.error(errMsg(err, "Failed to toggle payments."));
    } finally {
      setPayLoading(false);
    }
  }

  // ── Loading / Not found ───────────────────────────────────────────────

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonCard lines={3} />
        <SkeletonCard lines={5} />
        <SkeletonCard lines={4} />
      </div>
    );
  }
  if (!data) {
    return <div className="text-sm text-slate-500">Tenant not found.</div>;
  }

  const s = data.summary;
  const modules = [...new Set(features.map((f) => f.module))];

  // ── Render ────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <Link
        to="/provider/tenants"
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" /> All tenants
      </Link>

      <PageHeader
        title={s.name}
        description={s.owner_email}
        actions={
          <>
            <Badge tone="indigo">{s.subscription_plan}</Badge>
            {s.is_locked ? (
              <Badge tone="red">Locked</Badge>
            ) : (
              <Badge tone="green">{s.subscription_status || "active"}</Badge>
            )}
            <Button
              variant={s.is_locked ? "secondary" : "danger"}
              onClick={() => setPendingLock(true)}
            >
              {s.is_locked ? (
                <><LockOpen className="h-4 w-4" /> Unlock</>
              ) : (
                <><Lock className="h-4 w-4" /> Lock</>
              )}
            </Button>
          </>
        }
      />

      {/* Tab bar */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-xl w-fit">
        <TabBtn active={tab === "overview"} onClick={() => setTab("overview")}>
          <span className="flex items-center gap-1.5"><LayoutDashboard className="h-3.5 w-3.5" /> Overview</span>
        </TabBtn>
        <TabBtn active={tab === "pumps"} onClick={() => setTab("pumps")}>
          <span className="flex items-center gap-1.5"><Building2 className="h-3.5 w-3.5" /> Pumps</span>
        </TabBtn>
        <TabBtn active={tab === "subscription"} onClick={() => setTab("subscription")}>
          <span className="flex items-center gap-1.5"><CreditCard className="h-3.5 w-3.5" /> Subscription</span>
        </TabBtn>
        <TabBtn active={tab === "features"} onClick={() => setTab("features")}>
          <span className="flex items-center gap-1.5"><Zap className="h-3.5 w-3.5" /> Features</span>
        </TabBtn>
        <TabBtn active={tab === "payments"} onClick={() => setTab("payments")}>
          <span className="flex items-center gap-1.5"><Wallet className="h-3.5 w-3.5" /> Payments</span>
        </TabBtn>
      </div>

      {/* ── Overview tab ──────────────────────────────────────────────── */}
      {tab === "overview" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Plan", value: s.subscription_plan },
            { label: "Status", value: s.subscription_status || "active" },
            { label: "Pumps", value: String(s.pump_count) },
            { label: "Users", value: String(s.user_count) },
            { label: "Organisations", value: String(s.org_count) },
            {
              label: "Monthly Revenue",
              value: `₹${s.monthly_price_inr.toLocaleString("en-IN")}`,
            },
            { label: "Owner", value: s.owner_email },
            {
              label: "Created",
              value: new Date(s.created_at).toLocaleDateString("en-IN"),
            },
          ].map(({ label, value }) => (
            <Card key={label} className="py-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                {label}
              </p>
              <p className="text-sm font-semibold text-slate-900 truncate">{value}</p>
            </Card>
          ))}
        </div>
      )}

      {/* ── Pumps tab ─────────────────────────────────────────────────── */}
      {tab === "pumps" && (
        <Card>
          <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Building2 className="h-4 w-4 text-indigo-500" /> Pumps ({data.pumps.length})
          </h3>
          <div className="divide-y divide-slate-100">
            {data.pumps.map((p) => (
              <div
                key={p.id}
                className="py-2.5 flex items-center justify-between text-sm"
              >
                <div>
                  <div className="font-medium text-slate-900">{p.name}</div>
                  <div className="text-xs font-mono text-slate-500">
                    {p.code ?? "no code"}
                  </div>
                </div>
                <Badge tone={p.is_active ? "green" : "slate"}>
                  {p.is_active ? "active" : "inactive"}
                </Badge>
              </div>
            ))}
            {data.pumps.length === 0 && (
              <p className="py-3 text-sm text-slate-500">No pumps provisioned yet.</p>
            )}
          </div>
        </Card>
      )}

      {/* ── Subscription tab ──────────────────────────────────────────── */}
      {tab === "subscription" && (
        <div className="space-y-6">
          {/* Plan cards */}
          <Card>
            <h3 className="font-semibold text-slate-900 mb-4">Select Plan</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {PLANS.map((p) => {
                const isCurrent = s.subscription_plan === p.value;
                return (
                  <button
                    key={p.value}
                    type="button"
                    disabled={isCurrent || saving}
                    onClick={async () => {
                      setPlan(p.value);
                      setSaving(true);
                      try {
                        await providerApi.updateSubscription(id!, {
                          plan: p.value,
                          status: subStatus,
                          expires_at: expires ? new Date(expires).toISOString() : null,
                          monthly_price_inr: price,
                        });
                        toast.success(`Plan changed to ${p.value}.`);
                        await load();
                      } catch (err) {
                        toast.error(errMsg(err, "Failed to change plan."));
                      } finally {
                        setSaving(false);
                      }
                    }}
                    className={`relative text-left p-4 rounded-xl border-2 transition-all ${
                      isCurrent
                        ? "border-indigo-500 bg-indigo-50/70 ring-2 ring-indigo-500/20 cursor-default"
                        : "border-slate-200 hover:border-indigo-300 hover:shadow-sm bg-white cursor-pointer"
                    } ${saving && !isCurrent ? "opacity-50 cursor-wait" : ""}`}
                  >
                    {isCurrent && (
                      <div className="absolute top-2 right-2 flex items-center gap-1 bg-indigo-600 text-white text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full">
                        <Check className="h-2.5 w-2.5" /> Current
                      </div>
                    )}
                    <p className="font-bold text-base text-slate-900">{p.label}</p>
                    <p className="text-xs text-slate-500 mt-1">{p.desc}</p>
                    <p className="text-[10px] text-indigo-600 font-medium mt-2">{p.orgs}</p>
                  </button>
                );
              })}
            </div>
          </Card>

          {/* Subscription details form */}
          <Card>
            <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-indigo-500" /> Subscription Details
            </h3>
            <form onSubmit={saveSubscription} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Select
                label="Status"
                value={subStatus}
                onChange={(e) => setSubStatus(e.target.value)}
                options={STATUSES.map((v) => ({ value: v, label: v }))}
              />
              <Input
                label="Next billing date"
                type="date"
                value={expires}
                onChange={(e) => setExpires(e.target.value)}
              />
              <Input
                label="Monthly price (₹)"
                type="number"
                min={0}
                value={price}
                onChange={(e) => setPrice(Number(e.target.value) || 0)}
              />
              <div className="flex items-end">
                <Button type="submit" disabled={saving} className="w-full">
                  {saving ? "Saving…" : <><Save className="h-4 w-4" /> Save changes</>}
                </Button>
              </div>
            </form>

            {/* Read-only subscription summary */}
            <div className="mt-6 pt-5 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: "Plan", value: s.subscription_plan },
                { label: "Status", value: s.subscription_status || "active" },
                {
                  label: "Expires",
                  value: s.subscription_expires_at
                    ? new Date(s.subscription_expires_at).toLocaleDateString("en-IN")
                    : "—",
                },
                {
                  label: "Monthly (₹)",
                  value: `₹${s.monthly_price_inr.toLocaleString("en-IN")}`,
                },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                    {label}
                  </p>
                  <p className="text-sm font-semibold text-slate-800 mt-0.5">{value}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ── Features tab ──────────────────────────────────────────────── */}
      {tab === "features" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 p-3 bg-indigo-50 border border-indigo-100 rounded-xl text-xs text-indigo-700">
            <Zap className="h-3.5 w-3.5 shrink-0" />
            Overrides take priority over plan defaults. Core features are always
            on and cannot be changed. Hover a row to reveal the Reset button.
          </div>

          {featuresLoading && features.length === 0 ? (
            <SkeletonList rows={6} />
          ) : (
            modules.map((mod) => (
              <Card key={mod}>
                <h3 className="font-semibold text-slate-900 mb-3 text-sm">
                  {MODULE_LABELS[mod] ?? mod}
                </h3>
                <div className="space-y-0.5">
                  {features
                    .filter((f) => f.module === mod)
                    .map((f) => (
                      <div
                        key={f.id}
                        className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-slate-50 group transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-2 h-2 rounded-full shrink-0 ${
                              f.effective ? "bg-emerald-500" : "bg-red-400"
                            }`}
                          />
                          <div>
                            <p className="text-sm font-medium text-slate-900">{f.name}</p>
                            <p className="text-[10px] text-slate-400">
                              {f.is_core
                                ? "Always enabled (core)"
                                : f.source === "override"
                                ? `Override: ${f.override_enabled ? "force-enabled" : "force-disabled"}`
                                : f.source === "plan"
                                ? "Included in plan"
                                : "Not in plan"}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {f.is_core ? (
                            <span className="text-[10px] text-slate-400 font-semibold uppercase">
                              Core
                            </span>
                          ) : (
                            <>
                              <button
                                disabled={featuresLoading}
                                onClick={() => toggleFeature(f)}
                                className={`relative w-10 h-5 rounded-full transition-colors cursor-pointer disabled:opacity-50 ${
                                  f.effective ? "bg-emerald-500" : "bg-slate-300"
                                }`}
                              >
                                <span
                                  className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${
                                    f.effective ? "translate-x-5" : "translate-x-0"
                                  }`}
                                />
                              </button>
                              {f.override_enabled !== null && (
                                <button
                                  onClick={() => resetFeature(f)}
                                  disabled={featuresLoading}
                                  className="text-[10px] text-slate-400 hover:text-indigo-600 font-semibold uppercase tracking-wider opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-30"
                                >
                                  Reset
                                </button>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
              </Card>
            ))
          )}
        </div>
      )}

      {/* ── Payments tab ──────────────────────────────────────────────── */}
      {tab === "payments" && (
        <div className="space-y-4">
          {/* Status banner */}
          {payLoading && !payConfig ? (
            <SkeletonCard lines={5} />
          ) : (
            <>
              <div
                className={`flex items-center justify-between p-3 rounded-xl border text-sm ${
                  payConfig?.configured && payConfig.is_enabled
                    ? "bg-emerald-50 border-emerald-100 text-emerald-700"
                    : payConfig?.configured
                    ? "bg-amber-50 border-amber-100 text-amber-700"
                    : "bg-slate-50 border-slate-200 text-slate-500"
                }`}
              >
                <div>
                  <span className="font-semibold">
                    {payConfig?.configured && payConfig.is_enabled
                      ? "Online Payments: Enabled"
                      : payConfig?.configured
                      ? "Online Payments: Disabled"
                      : "Not Configured"}
                  </span>
                  {payConfig?.configured && (
                    <span className="ml-2 text-xs opacity-70">
                      {payConfig.gateway.toUpperCase()} · {payConfig.key_id_masked ?? "—"}
                    </span>
                  )}
                </div>
                {payConfig?.configured && (
                  <Button
                    variant="secondary"
                    onClick={togglePayments}
                    disabled={payLoading}
                    className="py-1 px-3 text-xs"
                  >
                    {payConfig.is_enabled ? "Disable" : "Enable"}
                  </Button>
                )}
              </div>

              {/* Config form */}
              <Card>
                <h3 className="font-semibold text-sm text-slate-900 mb-1 flex items-center gap-2">
                  <Wallet className="h-4 w-4 text-indigo-500" />
                  {payConfig?.configured
                    ? "Update Payment Credentials"
                    : "Configure Payment Gateway"}
                </h3>
                <p className="text-xs text-slate-500 mb-4">
                  Enter the merchant API credentials for this tenant's pump. Payments received
                  at the pump will be recorded automatically in the ERP once configured.
                </p>

                <form onSubmit={savePaymentConfig} className="space-y-3">
                  <Select
                    label="Gateway"
                    value={gateway}
                    onChange={(e) => setGateway(e.target.value)}
                    options={GATEWAYS}
                  />
                  <Input
                    label="Key ID / Merchant ID"
                    value={keyId}
                    onChange={(e) => setKeyId(e.target.value)}
                    placeholder={
                      gateway === "razorpay"
                        ? "rzp_live_xxxxxxxxxxxx"
                        : "mid_xxxxxxxxxxxx"
                    }
                    mono
                  />
                  <Input
                    label="Key Secret"
                    type="password"
                    value={keySecret}
                    onChange={(e) => setKeySecret(e.target.value)}
                    placeholder="Enter secret key"
                  />
                  <Input
                    label="Webhook Secret (optional)"
                    type="password"
                    value={webhookSecret}
                    onChange={(e) => setWebhookSecret(e.target.value)}
                    placeholder="whsec_…"
                  />

                  <div className="flex gap-2 pt-2 border-t border-slate-100">
                    <Button type="submit" disabled={payLoading}>
                      <Save className="h-4 w-4" />
                      {payLoading ? "Saving…" : "Save credentials"}
                    </Button>
                    {payConfig?.configured && (
                      <Button
                        variant="danger"
                        type="button"
                        onClick={removePaymentConfig}
                        disabled={payLoading}
                      >
                        <Trash2 className="h-4 w-4" /> Remove config
                      </Button>
                    )}
                  </div>
                </form>
              </Card>
            </>
          )}
        </div>
      )}

      {/* ── Danger zone ───────────────────────────────────────────────── */}
      <Card className="border-red-200 bg-red-50/40">
        <h3 className="font-semibold text-red-700 mb-2 flex items-center gap-2">
          <AlertOctagon className="h-4 w-4" /> Danger zone
        </h3>
        <p className="text-sm text-slate-600 mb-4">
          Permanently delete this tenant and every record it owns — pumps, shifts,
          transactions and audit logs. This cannot be undone.
        </p>
        <Button
          variant="danger"
          onClick={() => {
            setDeleteConfirm("");
            setShowDelete(true);
          }}
        >
          <Trash2 className="h-4 w-4" /> Delete tenant permanently
        </Button>
      </Card>

      {/* ── Dialogs ───────────────────────────────────────────────────── */}
      <ConfirmDialog
        open={pendingLock}
        title={s.is_locked ? "Unlock tenant?" : "Lock tenant?"}
        message={
          s.is_locked
            ? `Unlocking ${s.name} restores API access for all its users.`
            : `Locking ${s.name} blocks all its users immediately.`
        }
        destructive={!s.is_locked}
        busy={lockBusy}
        confirmLabel={s.is_locked ? "Unlock" : "Lock"}
        onCancel={() => setPendingLock(false)}
        onConfirm={confirmLockToggle}
      />

      <Modal
        open={showDelete}
        onClose={() => (deleting ? undefined : setShowDelete(false))}
        title="Permanently delete tenant"
        widthClass="max-w-md"
      >
        <div className="space-y-3">
          <p className="text-sm text-slate-700">
            This removes <span className="font-semibold">{s.name}</span> and every
            record it owns — pumps, shifts, transactions, audit logs — forever.
            There is no undo.
          </p>
          <p className="text-sm text-slate-700">Type the tenant name to confirm.</p>
          <Input
            label={`Type "${s.name}" to confirm`}
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder={s.name}
            autoFocus
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button
            variant="secondary"
            onClick={() => setShowDelete(false)}
            disabled={deleting}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={deleting || deleteConfirm.trim() !== s.name.trim()}
            onClick={async () => {
              if (!id) return;
              setDeleting(true);
              try {
                await providerApi.deleteTenant(id, deleteConfirm.trim());
                toast.success(`Tenant "${s.name}" deleted.`);
                navigate("/provider/tenants", { replace: true });
              } catch (err) {
                toast.error(errMsg(err, "Failed to delete tenant."));
              } finally {
                setDeleting(false);
              }
            }}
          >
            {deleting ? "Deleting…" : "Delete permanently"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
