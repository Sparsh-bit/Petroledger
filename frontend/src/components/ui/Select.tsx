import { SelectHTMLAttributes, ReactNode } from "react";

function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options?: SelectOption[];
  placeholder?: string;
  children?: ReactNode;
}

export function Select({
  label,
  error,
  options,
  placeholder,
  className,
  id,
  children,
  ...props
}: SelectProps) {
  const selectId = id || props.name || label;
  return (
    <div className="space-y-1.5">
      {label && (
        <label
          htmlFor={selectId}
          className="block text-xs font-medium uppercase tracking-wide text-slate-600"
        >
          {label}
        </label>
      )}
      <select
        id={selectId}
        className={cx(
          "w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition focus:border-slate-400",
          error ? "border-red-500" : "border-slate-300",
          className,
        )}
        aria-invalid={!!error}
        aria-describedby={error ? `${selectId}-err` : undefined}
        {...props}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options
          ? options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))
          : children}
      </select>
      {error && (
        <p id={`${selectId}-err`} className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

/** Native text input styled for light portal screens (matches Select). */
export function LightInput(
  props: React.InputHTMLAttributes<HTMLInputElement> & {
    label?: string;
    error?: string;
  },
) {
  const { label, error, className, id, ...rest } = props;
  const inputId = id || rest.name || label;
  return (
    <div className="space-y-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-xs font-medium uppercase tracking-wide text-slate-600"
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={cx(
          "w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-slate-400",
          error ? "border-red-500" : "border-slate-300",
          className,
        )}
        aria-invalid={!!error}
        {...rest}
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
