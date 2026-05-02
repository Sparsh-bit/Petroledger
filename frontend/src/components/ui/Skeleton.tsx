import { HTMLAttributes } from "react";

function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  /** Shortcut to set width / height via Tailwind classes. */
  className?: string;
}

/**
 * Generic shimmer block. Compose with width/height utility classes:
 *   <Skeleton className="h-6 w-40" />
 *   <Skeleton className="h-24 w-full rounded-xl" />
 */
export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={cx(
        "relative overflow-hidden rounded-md bg-slate-200/80",
        "before:absolute before:inset-0 before:-translate-x-full",
        "before:animate-[shimmer_1.6s_infinite]",
        "before:bg-gradient-to-r before:from-transparent before:via-white/60 before:to-transparent",
        className,
      )}
      {...props}
    />
  );
}

/** Convenience: a vertical stack of skeleton rows. */
export function SkeletonList({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

/** Grid of KPI-card skeletons for dashboards. */
export function SkeletonKpiGrid({ cards = 4 }: { cards?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: cards }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3"
        >
          <div className="flex items-center justify-between">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-8 w-8 rounded-lg" />
          </div>
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-3 w-32" />
        </div>
      ))}
    </div>
  );
}

/** Generic card-body skeleton — use inside Card components whose
 *  surrounding chrome (title, actions) is already rendered. */
export function SkeletonCard({ lines = 4 }: { lines?: number }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={i === 0 ? "h-5 w-1/3" : "h-4 w-full"}
        />
      ))}
    </div>
  );
}
