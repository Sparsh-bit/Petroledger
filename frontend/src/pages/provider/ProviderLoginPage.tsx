import { FormEvent, useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, ShieldCheck, Layers, Activity, Lock } from "lucide-react";

import { Button, Input } from "../../components/ui";
import { loginRequest } from "../../api/auth";
import { useAuth } from "../../store/auth";

export default function ProviderLoginPage() {
  const navigate = useNavigate();
  const { user, accessToken, setTokens, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (accessToken && user && (user.role === "superadmin" || user.role === "provider")) {
      navigate("/provider/dashboard", { replace: true });
    }
  }, [accessToken, user, navigate]);

  if (accessToken && user && (user.role === "superadmin" || user.role === "provider")) {
    return <Navigate to="/provider/dashboard" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await loginRequest({
        email: email.trim(),
        password,
      });
      if (res.user.role !== "superadmin" && res.user.role !== "provider") {
        setError("This portal is for platform operators only");
        setLoading(false);
        return;
      }
      setTokens(res.access_token, res.refresh_token);
      setUser(res.user);
      navigate("/provider/dashboard", { replace: true });
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
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-slate-950 text-slate-100">
      {/* LEFT — Form */}
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 mb-10"
          >
            <ArrowLeft className="h-4 w-4" /> Back to home
          </Link>

          <div className="flex items-center gap-2 font-bold text-lg">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-300">
              <Lock className="h-4 w-4" />
            </span>
            Petro<span className="text-indigo-300">Ledger</span>
            <span className="ml-2 rounded-full border border-indigo-500/40 bg-indigo-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-indigo-200">
              Operator
            </span>
          </div>
          <h1 className="mt-8 text-3xl font-bold tracking-tight">
            Provider Portal
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            PetroLedger Operations — platform administration for superadmins
            and provider staff.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate>
            <Input
              label="Email"
              name="email"
              type="email"
              autoComplete="email"
              required
              placeholder="you@petroledger.in"
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

            <div className="flex justify-between text-xs text-slate-400">
              <Link to="/forgot-password" className="hover:text-slate-200">
                Forgot password?
              </Link>
              <Link to="/login" className="hover:text-slate-200">
                Pump staff? → /login
              </Link>
            </div>
          </form>
        </div>
      </div>

      {/* RIGHT — Brand panel */}
      <div className="relative hidden lg:block overflow-hidden border-l border-slate-900">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(99,102,241,0.25),transparent_60%)]" />
        <div className="relative h-full flex flex-col justify-between p-12">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/40 bg-slate-950/50 px-3 py-1 text-xs text-indigo-200">
              <ShieldCheck className="h-3 w-3" /> Restricted — operators only
            </div>
            <h2 className="mt-6 text-4xl font-bold leading-tight">
              Run the platform. <br />
              <span className="text-indigo-300">Not just a pump.</span>
            </h2>
            <p className="mt-4 text-slate-300 max-w-md">
              Manage tenants, subscriptions, and global controls across every
              PetroLedger deployment.
            </p>
          </motion.div>

          <div className="grid gap-3">
            {[
              {
                icon: Layers,
                title: "Multi-tenant control",
                text: "Provision and suspend organizations on demand.",
              },
              {
                icon: Activity,
                title: "Live platform health",
                text: "Ingestion, reconciliation, and cron status at a glance.",
              },
              {
                icon: ShieldCheck,
                title: "Audit-grade access",
                text: "Every operator action signed and logged.",
              },
            ].map((c, i) => (
              <motion.div
                key={c.title}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + i * 0.08 }}
                className="flex gap-3 rounded-xl border border-slate-800/80 bg-slate-950/40 backdrop-blur-sm p-4"
              >
                <c.icon className="h-5 w-5 text-indigo-300 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-sm">{c.title}</div>
                  <div className="text-xs text-slate-400">{c.text}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
