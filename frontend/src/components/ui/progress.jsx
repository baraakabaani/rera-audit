import { cn } from "../../lib/utils";

// Stacked segmented progress bar: segments = [{ value, className }]
export function SegmentedBar({ segments, total, className }) {
  const sum = total || segments.reduce((a, s) => a + s.value, 0) || 1;
  return (
    <div className={cn("flex h-2.5 w-full overflow-hidden rounded-full bg-slate-100", className)}>
      {segments.map((s, i) => (
        <div
          key={i}
          className={cn("h-full transition-all", s.className)}
          style={{ width: `${(s.value / sum) * 100}%` }}
        />
      ))}
    </div>
  );
}
