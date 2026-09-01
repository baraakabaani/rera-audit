import { cn } from "../../lib/utils";

const tones = {
  Received: "bg-emerald-100 text-emerald-700 ring-emerald-600/20",
  Partial: "bg-amber-100 text-amber-700 ring-amber-600/20",
  Pending: "bg-rose-100 text-rose-700 ring-rose-600/20",
  "Not applicable": "bg-slate-100 text-slate-500 ring-slate-500/20",
  neutral: "bg-slate-100 text-slate-600 ring-slate-500/20",
  info: "bg-brand-100 text-brand-700 ring-brand-600/20",
};

export function Badge({ tone = "neutral", className, children }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        tones[tone] || tones.neutral,
        className
      )}
    >
      {children}
    </span>
  );
}
