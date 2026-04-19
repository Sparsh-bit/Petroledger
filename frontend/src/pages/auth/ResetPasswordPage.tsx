import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Fuel } from "lucide-react";
import { Button, Input } from "../../components/ui";
import { api } from "../../api/client";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!token) {
      setError("Missing reset token. Please use the link from your email.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/password-reset/confirm", {
        token,
        new_password: password,
      });
      setDone(true);
      setTimeout(() => navigate("/login", { replace: true }), 1800);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data
          ?.message ||
        (err as { message?: string })?.message ||
        "Could not reset password.";
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
          Reset password
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Choose a new password. Must be 8+ characters with an uppercase letter,
          a digit, and a special character.
        </p>

        {done ? (
          <div className="mt-8 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-4 text-sm text-emerald-700">
            Password updated. Redirecting to sign in…
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
            <Input
              label="New password"
              name="new_password"
              type="password"
              autoComplete="new-password"
              required
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Input
              label="Confirm new password"
              name="confirm_password"
              type="password"
              autoComplete="new-password"
              required
              placeholder="••••••••"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
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
              {loading ? "Updating…" : "Update password"}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
