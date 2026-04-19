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
