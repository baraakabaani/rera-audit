import { Check } from "lucide-react";
import { cn } from "../lib/utils";

const STEPS = [
  { n: 1, label: "Requirements & Template" },
  { n: 2, label: "Customer Files & Matcher" },
  { n: 3, label: "Review & Export" },
];

export function StepIndicator({ step, maxStep, onJump }) {
  return (
    <ol className="flex items-center gap-2 sm:gap-4">
      {STEPS.map((s, i) => {
        const done = s.n < step;
        const active = s.n === step;
        const reachable = s.n <= maxStep;
        return (
          <li key={s.n} className="flex flex-1 items-center gap-2 sm:gap-4">
            <button
              disabled={!reachable}
              onClick={() => reachable && onJump(s.n)}
              className={cn(
                "flex items-center gap-2 rounded-lg px-2 py-1 text-left transition-colors",
                reachable ? "hover:bg-slate-100" : "cursor-not-allowed opacity-50"
              )}
            >
              <span
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                  done && "bg-emerald-600 text-white",
                  active && "bg-brand-600 text-white",
                  !done && !active && "bg-slate-200 text-slate-600"
                )}
              >
                {done ? <Check className="h-4 w-4" /> : s.n}
              </span>
              <span
                className={cn(
                  "hidden text-sm font-medium sm:block",
                  active ? "text-slate-900" : "text-slate-500"
                )}
              >
                {s.label}
              </span>
            </button>
            {i < STEPS.length - 1 && <div className="h-px flex-1 bg-slate-200" />}
          </li>
        );
      })}
    </ol>
  );
}
