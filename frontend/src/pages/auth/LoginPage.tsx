import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Fuel, KeyRound, ShieldCheck } from "lucide-react";

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
        (err as { response?: { data?: { detail?: string; message?: string } }; message?: string })
          ?.response?.data?.detail ||
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        (err as { message?: string })?.message ||
        "Login failed. Please check your credentials.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-slate-50">
      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-10"
          >
            <ArrowLeft className="h-4 w-4" /> Back to home
          </Link>

          <div className="flex items-center gap-2.5">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 text-white shadow-sm">
              <Fuel className="h-4 w-4" />
            </span>
            <div className="font-bold text-lg text-slate-900">
              Petro<span className="text-indigo-600">Ledger</span>
            </div>
          </div>
          <h1 className="mt-8 text-2xl font-bold tracking-tight text-slate-900">
            Welcome back
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Enter your pump code, email, and password to sign in.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
            <Input
              label="Pump Code"
              name="pump_code"
              placeholder="MUM-BAN-042"
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
                className="rounded-xl border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700"
              >
                {error}
              </div>
            )}

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Signing in…" : "Sign in"}
            </Button>

            <div className="flex justify-between text-xs text-slate-500">
              <Link to="/forgot-password" className="hover:text-slate-900">
                Forgot password?
              </Link>
              <span>support@petroledger.in</span>
            </div>
            <div className="pt-4 border-t border-slate-100 text-center text-xs text-slate-500">
              Platform operator?{" "}
              <Link
                to="/provider"
                className="font-semibold text-indigo-600 hover:text-indigo-500"
              >
                Sign in here →
              </Link>
            </div>
          </form>
        </div>
      </div>

      <div className="relative hidden lg:block border-l border-slate-100 bg-white">
        <div className="h-full flex flex-col justify-between p-12">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
              <ShieldCheck className="h-3 w-3" /> Trusted by 500+ pumps
            </div>
            <h2 className="mt-8 text-3xl font-bold leading-tight text-slate-900">
              Close your day before <br />
              <span className="text-indigo-600">the day closes you.</span>
            </h2>
            <p className="mt-3 text-sm text-slate-500 max-w-md">
              Reconcile, audit, and report — all from one cockpit, built for
              Indian forecourts.
            </p>
          </div>

          <div className="grid gap-3">
            {[
              {
                icon: KeyRound,
                title: "Pump-code sign-in",
                text: "Every login scoped to a specific pump — no cross-tenant leakage.",
              },
              {
                icon: ShieldCheck,
                title: "Bank-grade security",
                text: "Every action hashed and signed.",
              },
            ].map((c) => (
              <div
                key={c.title}
                className="flex gap-3 rounded-xl border border-slate-100 bg-slate-50 p-4"
              >
                <c.icon className="h-5 w-5 text-indigo-600 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold text-sm text-slate-900">
                    {c.title}
                  </div>
                  <div className="text-xs text-slate-500">{c.text}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
