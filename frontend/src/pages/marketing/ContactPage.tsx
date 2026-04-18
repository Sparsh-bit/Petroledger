import { FormEvent, useState } from "react";
import toast from "react-hot-toast";
import { MarketingLayout } from "@/components/landing/MarketingLayout";
import { contactApi } from "@/api/contact";

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await contactApi.submit({
        name: name.trim(),
        email: email.trim(),
        company: company.trim() || undefined,
        message: message.trim(),
      });
      toast.success(res.message);
      setDone(true);
      setName("");
      setEmail("");
      setCompany("");
      setMessage("");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Could not submit — please try again.";
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
        Get in touch
      </h1>
      <p className="mt-4 text-lg text-slate-400 max-w-xl">
        Tell us about your pump or chain. We reply within one business day.
      </p>

      <div className="mt-8 grid gap-3 sm:grid-cols-3 max-w-3xl">
        <a
          href="mailto:official.concilio@gmail.com"
          className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm hover:border-amber-400/40 transition"
        >
          <div className="text-xs uppercase tracking-wider text-slate-500">Email</div>
          <div className="mt-1 text-slate-100 font-medium">official.concilio@gmail.com</div>
        </a>
        <a
          href="tel:+918840268280"
          className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm hover:border-amber-400/40 transition"
        >
          <div className="text-xs uppercase tracking-wider text-slate-500">Phone</div>
          <div className="mt-1 text-slate-100 font-medium">+91 88402 68280</div>
        </a>
        <a
          href="https://concilio.solutions"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm hover:border-amber-400/40 transition"
        >
          <div className="text-xs uppercase tracking-wider text-slate-500">Website</div>
          <div className="mt-1 text-slate-100 font-medium">concilio.solutions</div>
        </a>
      </div>

      {done ? (
        <div className="mt-10 rounded-2xl border border-emerald-400/30 bg-emerald-400/5 p-6 text-emerald-200">
          Thanks — your message is in. We'll be in touch shortly.
          <button
            onClick={() => setDone(false)}
            className="block mt-4 text-sm underline hover:text-white"
          >
            Send another
          </button>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="mt-10 grid grid-cols-1 gap-4 max-w-xl">
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Name
            </label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputCls}
              placeholder="Your name"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Email
            </label>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputCls}
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Company / Pump name
            </label>
            <input
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className={inputCls}
              placeholder="Optional"
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-slate-400 mb-1.5">
              Message
            </label>
            <textarea
              required
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={6}
              className={inputCls}
              placeholder="Tell us a bit about what you're looking for…"
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="mt-2 inline-flex justify-center items-center h-12 px-6 rounded-full bg-amber-400 text-slate-950 font-medium hover:bg-amber-300 disabled:opacity-60 transition"
          >
            {busy ? "Sending…" : "Send message"}
          </button>
        </form>
      )}
    </MarketingLayout>
  );
}
