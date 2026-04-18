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
    "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed";
  const variants: Record<ButtonVariant, string> = {
    primary:
      "bg-brand-500 text-ink-950 hover:bg-brand-400 shadow-glow focus-visible:ring-2 ring-brand-300",
    secondary:
      "bg-ink-800 text-ink-100 hover:bg-ink-700 border border-ink-700",
    ghost: "text-ink-200 hover:bg-ink-800/60",
    danger: "bg-red-600 text-white hover:bg-red-500",
  };
  return <button className={cx(base, variants[variant], className)} {...props} />;
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  mono?: boolean;
}

export function Input({ label, error, mono, className, id, ...props }: InputProps) {
  const inputId = id || props.name || label;
  return (
    <div className="space-y-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-xs font-medium uppercase tracking-wide text-ink-400"
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={cx(
          "w-full rounded-lg border bg-ink-900/60 px-3.5 py-2.5 text-sm text-ink-50 placeholder:text-ink-500 outline-none transition focus:border-brand-400 focus:bg-ink-900",
          error ? "border-red-500" : "border-ink-700",
          mono && "font-mono tracking-wider uppercase",
          className,
        )}
        aria-invalid={!!error}
        aria-describedby={error ? `${inputId}-err` : undefined}
        {...props}
      />
      {error && (
        <p id={`${inputId}-err`} className="text-xs text-red-400">
          {error}
        </p>
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
        "rounded-2xl border border-ink-800 bg-ink-900/50 backdrop-blur-sm p-6",
        className,
      )}
      {...props}
    />
  );
}

type BadgeTone = "green" | "amber" | "red" | "slate" | "blue";

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
    green: "bg-brand-500/15 text-brand-300 border-brand-500/30",
    amber: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    red: "bg-red-500/15 text-red-300 border-red-500/30",
    slate: "bg-ink-700/40 text-ink-300 border-ink-600",
    blue: "bg-sky-500/15 text-sky-300 border-sky-500/30",
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
