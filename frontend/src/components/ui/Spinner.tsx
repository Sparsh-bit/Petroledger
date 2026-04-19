import { Loader2 } from "lucide-react";

export function Spinner({
  size = 20,
  className,
  label,
}: {
  size?: number;
  className?: string;
  label?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`inline-flex items-center gap-2 text-slate-500 ${className ?? ""}`}
    >
      <Loader2 className="animate-spin" style={{ width: size, height: size }} />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}

export function FullPageSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex min-h-[40vh] w-full items-center justify-center">
      <Spinner size={28} label={label} />
    </div>
  );
}
