import { cn } from "@/lib/utils";
import type { TrackingWindowInput } from "@/types/api";
import { DAYS_LONG, DAYS_SHORT, weekSegments } from "@/utils/schedule";

interface Props {
  windows: TrackingWindowInput[];
  /** Highlight today's column (0 = Monday). */
  today?: number;
  className?: string;
}

/** Compact weekly coverage: one 24h track per day, filled where tracking is on. */
export function WeekStrip({ windows, today, className }: Props) {
  const days = weekSegments(windows);
  return (
    <div className={cn("grid grid-cols-7 gap-1", className)} role="img" aria-label="Haftalık takip takvimi">
      {days.map((segments, day) => (
        <div key={day} className="min-w-0 space-y-1">
          <div
            className={cn(
              "text-center text-[10px] font-medium",
              day === today ? "text-primary" : "text-muted-foreground",
            )}
          >
            {DAYS_SHORT[day]}
          </div>
          <div
            className={cn("bg-muted relative h-2 overflow-hidden rounded-full", day === today && "ring-primary/40 ring-1")}
            title={`${DAYS_LONG[day]}: ${segments.length ? "takip var" : "takip yok"}`}
          >
            {segments.map(([start, end], i) => (
              <div
                key={i}
                className="bg-primary absolute inset-y-0"
                style={{ left: `${(start / 1440) * 100}%`, width: `${((end - start) / 1440) * 100}%` }}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
