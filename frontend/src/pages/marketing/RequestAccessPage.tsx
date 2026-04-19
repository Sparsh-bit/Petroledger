import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { Loader2, CheckCircle2, ArrowRight } from "lucide-react";
import { MarketingLayout } from "@/components/landing/MarketingLayout";
import {
  accessRequestsApi,
  PumpCountRange,
} from "@/api/access-requests";

const PUMP_RANGES: { value: PumpCountRange; label: string }[] = [
  { value: "1", label: "1 pump" },
  { value: "2-5", label: "2 – 5 pumps" },
  { value: "6-10", label: "6 – 10 pumps" },
  { value: "11-25", label: "11 – 25 pumps" },
  { value: "25+", label: "25+ pumps" },
];

const PHONE_RE = /^\+91[\s-]?[6-9]\d{9}$/;

export default function RequestAccessPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("+91 ");
  const [company, setCompany] = useState("");
  const [pumpRange, setPumpRange] = useState<PumpCountRange>("1");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [message, setMessage] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!PHONE_RE.test(phone.trim())) {
      toast.error("Enter a valid Indian phone number, e.g. +91 9876543210");
      return;
    }
    if (!consent) {
      toast.error("Please agree to be contacted.");
      return;
    }
    setBusy(true);
    try {
      const res = await accessRequestsApi.submit({
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim(),
        company: company.trim(),
        pump_count_range: pumpRange,
        city: city.trim(),
        state: state.trim(),
        message: message.trim() || undefined,
        consent,
      });
      toast.success(res.message);
      setDone(true);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: unknown } } })?.response?.data
          ?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : "Could not submit — please try again.";
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  const inputCls =
    "w-full rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-amber-400/60 focus:bg-white/[0.05]";

  return (
    <MarketingLayout>
      <h1 className="font-display font-bold text-4xl md:text-5xl tracking-tight">
        Request access
      </h1>
      <p className="mt-4 text-lg text-slate-400 max-w-xl">
        Tell us about your pump. We'll reach out within 24 hours to set up
        your tenant and walk through onboarding.
      </p>

      {done ? (
        <div className="mt-10 max-w-xl rounded-2xl border border-emerald-400/30 bg-emerald-400/5 p-8">
          <div className="flex items-start gap-4">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-emerald-400/15 ring-1 ring-emerald-400/40">
              <CheckCircle2 className="h-5 w-5 text-emerald-300" />
            </span>
            <div>
              <h2 className="font-display text-xl font-semibold text-emerald-100">
                Thanks — we'll reach out within 24 hours
              </h2>
              <p className="mt-2 text-sm text-emerald-200/80 leading-relaxed">
                A member of the PetroLedger team will email and call you to
                confirm your details, provision your tenant, and schedule a
                short onboarding session.
              </p>
              <ul className="mt-4 text-sm text-emerald-200/70 space-y-1.5 list-disc list-inside">
                <li>Tenant + owner login created</li>
                <li>Pumps and nozzles configured</li>
                <li>First reconciliation walkthrough</li>
              </ul>
              <Link
                to="/"
                className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-amber-300 hover:text-amber-200"
              >
                Back to home
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </div>
      ) : (
        <form
          onSubmit={onSubmit}
          className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl"
        >
          <div className="md:col-span-1">
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Full name
            </label>
            <input
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className={inputCls}
              placeholder="Your name"
            />
          </div>
          <div className="md:col-span-1">
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Work email
            </label>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputCls}
              placeholder="you@yourpump.com"
            />
          </div>
          <div className="md:col-span-1">
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Phone
            </label>
            <input
              required
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className={inputCls}
              placeholder="+91 9876543210"
            />
          </div>
          <div className="md:col-span-1">
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Company / Petrol pump name
            </label>
            <input
              required
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className={inputCls}
              placeholder="e.g. Sharma Auto Fuels"
            />
          </div>
          <div className="md:col-span-1">
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Number of pumps
            </label>
            <select
              required
              value={pumpRange}
              onChange={(e) => setPumpRange(e.target.value as PumpCountRange)}
              className={inputCls}
            >
              {PUMP_RANGES.map((p) => (
                <option key={p.value} value={p.value} className="bg-slate-900">
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-1 grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
                City
              </label>
              <input
                required
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className={inputCls}
                placeholder="Bengaluru"
              />
            </div>
            <div>
              <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
                State
              </label>
              <input
                required
                value={state}
                onChange={(e) => setState(e.target.value)}
                className={inputCls}
                placeholder="Karnataka"
              />
            </div>
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Message / requirements (optional)
            </label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={5}
              className={inputCls}
              placeholder="Anything specific you'd like us to know?"
            />
          </div>
          <label className="md:col-span-2 flex items-start gap-3 text-sm text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-white/20 bg-white/5 text-amber-400 focus:ring-amber-400/40"
            />
            <span>
              I agree to be contacted by the PetroLedger team about my access
              request.
            </span>
          </label>
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={busy}
              className="inline-flex justify-center items-center h-12 px-7 rounded-full bg-amber-400 text-slate-950 font-medium hover:bg-amber-300 disabled:opacity-60 transition"
            >
              {busy ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Submitting…
                </>
              ) : (
                "Request access"
              )}
            </button>
          </div>
        </form>
      )}
    </MarketingLayout>
  );
}
