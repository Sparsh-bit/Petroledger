import { ButtonHTMLAttributes, InputHTMLAttributes, HTMLAttributes } from "react";

function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed";
  const variants: Record<ButtonVariant, string> = {
    primary:
      "bg-indigo-600 text-white hover:bg-indigo-500 shadow-sm shadow-indigo-200",
    secondary:
      "bg-white text-slate-700 hover:bg-slate-50 border border-slate-200",
    ghost: "text-slate-600 hover:bg-slate-100",
    danger: "bg-red-600 text-white hover:bg-red-500",
  };
  return <button className={cx(base, variants[variant], className)} {...props} />;
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  mono?: boolean;
}

export function Input({ label, error, hint, mono, className, id, ...props }: InputProps) {
  const inputId = id || props.name || label;
  return (
    <div className="space-y-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-[11px] font-semibold uppercase tracking-widest text-slate-500"
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={cx(
          "w-full h-10 rounded-xl border bg-white px-3.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/10",
          error ? "border-red-500" : "border-slate-200",
          mono && "font-mono tracking-wider uppercase",
          className,
        )}
        aria-invalid={!!error}
        aria-describedby={error ? `${inputId}-err` : undefined}
        {...props}
      />
      {error && (
        <p id={`${inputId}-err`} className="text-xs text-red-600">
          {error}
        </p>
      )}
      {!error && hint && (
        <p className="text-xs text-slate-400">{hint}</p>
      )}
    </div>
  );
}

export function Card({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        "rounded-xl border border-slate-100 bg-white p-5 shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

type BadgeTone = "green" | "amber" | "red" | "slate" | "blue" | "indigo";

export function Badge({
  tone = "slate",
  children,
  className,
}: {
  tone?: BadgeTone;
  children: React.ReactNode;
  className?: string;
}) {
  const tones: Record<BadgeTone, string> = {
    green: "bg-emerald-50 text-emerald-700 border-emerald-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    red: "bg-red-50 text-red-700 border-red-200",
    slate: "bg-slate-50 text-slate-600 border-slate-200",
    blue: "bg-sky-50 text-sky-700 border-sky-200",
    indigo: "bg-indigo-50 text-indigo-700 border-indigo-200",
  };
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
