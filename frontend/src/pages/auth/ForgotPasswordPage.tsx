import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Fuel } from "lucide-react";
import { Button, Input } from "../../components/ui";
import { api } from "../../api/client";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.post("/auth/password-reset/request", { email: email.trim() });
      setSent(true);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ||
        (err as { message?: string })?.message ||
        "Something went wrong. Try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-6 py-12">
      <div className="w-full max-w-md">
        <Link
          to="/login"
          className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-10"
        >
          <ArrowLeft className="h-4 w-4" /> Back to sign in
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
          Forgot password
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Enter your email and we&apos;ll send you a link to reset your password.
        </p>

        {sent ? (
          <div className="mt-8 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-4 text-sm text-emerald-700">
            Check your email — if an account exists for{" "}
            <span className="font-mono">{email}</span>, a reset link is on its
            way.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
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
            {error && (
              <div
                role="alert"
                className="rounded-xl border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700"
              >
                {error}
              </div>
            )}
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Sending…" : "Send reset link"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
