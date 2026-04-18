import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, Fuel, ShieldCheck, Sparkles, Zap } from "lucide-react";

import { Button, Input } from "../../components/ui";
import { loginRequest } from "../../api/auth";
import { roleHomePath, useAuth } from "../../store/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuth();
  const [pumpCode, setPumpCode] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await loginRequest({
        email: email.trim(),
        password,
        pump_code: pumpCode.trim() || undefined,
      });
      setTokens(res.access_token, res.refresh_token);
      setUser(res.user);
      navigate(roleHomePath(res.user.role), { replace: true });
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } }; message?: string })
          ?.response?.data?.message ||
        (err as { message?: string })?.message ||
        "Login failed. Please check your credentials.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-ink-950 text-ink-100">
      {/* LEFT — Form */}
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm text-ink-400 hover:text-ink-200 mb-10"
          >
            <ArrowLeft className="h-4 w-4" /> Back to home
          </Link>

          <div className="flex items-center gap-2 font-bold text-lg">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/20 text-brand-300">
              <Fuel className="h-4 w-4" />
            </span>
            Petro<span className="text-brand-400">Ledger</span>
          </div>
          <h1 className="mt-8 text-3xl font-bold tracking-tight">
            Welcome back
          </h1>
          <p className="mt-2 text-sm text-ink-400">
            Sign in with your pump code and credentials. Provider staff can
            leave the pump code blank.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate>
            <Input
              label="Pump Code"
              name="pump_code"
              placeholder="e.g. MUM-BAN-042"
              autoComplete="off"
              value={pumpCode}
              onChange={(e) => setPumpCode(e.target.value.toUpperCase())}
              mono
            />
            <Input
              label="Email"
              name="email"
              type="email"
              autoComplete="email"
              required
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />

            {error && (
              <div
                role="alert"
                className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300"
              >
                {error}
              </div>
            )}

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Signing in…" : "Sign In"}
            </Button>

            <div className="flex justify-between text-xs text-ink-400">
              <Link to="/forgot-password" className="hover:text-ink-200">
                Forgot password?
              </Link>
              <span>Need help? support@petroledger.in</span>
            </div>
            <div className="pt-4 border-t border-ink-900 text-center text-xs text-ink-500">
              Platform operator?{" "}
              <Link to="/provider" className="text-brand-300 hover:text-brand-200">
                Sign in here →
              </Link>
            </div>
          </form>
        </div>
      </div>

      {/* RIGHT — Brand panel */}
      <div className="relative hidden lg:block overflow-hidden border-l border-ink-900">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-500/30 via-emerald-500/10 to-sky-500/20" />
        <div className="absolute inset-0 grid-bg opacity-30" />
        <div className="relative h-full flex flex-col justify-between p-12">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-brand-500/40 bg-ink-950/50 px-3 py-1 text-xs text-brand-200">
              <Sparkles className="h-3 w-3" /> Trusted by 500+ pumps
            </div>
            <h2 className="mt-6 text-4xl font-bold leading-tight">
              Close your day <br />
              <span className="text-brand-300">before the day closes you.</span>
            </h2>
            <p className="mt-4 text-ink-300 max-w-md">
              Reconcile, audit, and report — all from one cockpit, built for
              Indian forecourts.
            </p>
          </motion.div>

          <div className="grid gap-3">
            {[
              {
                icon: ShieldCheck,
                title: "Bank-grade security",
                text: "Every action hashed and signed.",
              },
              {
                icon: Zap,
                title: "Built for mobile",
                text: "Workers in the field, not at a desk.",
              },
              {
                icon: Sparkles,
                title: "Insights that pay for themselves",
                text: "Catch shrinkage before the week ends.",
              },
            ].map((c, i) => (
              <motion.div
                key={c.title}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.08 }}
                className="flex gap-3 rounded-xl border border-ink-800/80 bg-ink-950/40 backdrop-blur-sm p-4"
              >
                <c.icon className="h-5 w-5 text-brand-300 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-sm">{c.title}</div>
                  <div className="text-xs text-ink-400">{c.text}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
