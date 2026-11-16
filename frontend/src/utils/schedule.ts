import type { TrackingState, TrackingWindowInput } from "@/types/api";

export const DAYS_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
export const DAYS_LONG = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];

export const STATE_META: Record<
  TrackingState,
  { label: string; variant: "success" | "warning" | "destructive" | "muted" | "secondary" }
> = {
  live: { label: "Canlı", variant: "destructive" },
  offline: { label: "Çevrimdışı", variant: "secondary" },
  outside_schedule: { label: "Takvim dışı", variant: "muted" },
  inactive: { label: "Pasif", variant: "muted" },
  not_configured: { label: "API ayarı yok", variant: "warning" },
  unsupported: { label: "Desteklenmiyor", variant: "muted" },
  error: { label: "Hata", variant: "destructive" },
  pending: { label: "Bekleniyor", variant: "muted" },
};

const HHMM = /^([01]\d|2[0-3]):([0-5]\d)$/;

export function isValidTime(value: string): boolean {
  return HHMM.test(value);
}

export function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

export function crossesMidnight(w: TrackingWindowInput): boolean {
  return toMinutes(w.end_time) <= toMinutes(w.start_time);
}

export function formatWindow(w: TrackingWindowInput): string {
  if (w.start_time === w.end_time) return `${DAYS_SHORT[w.day_of_week]} 24 saat`;
  const next = crossesMidnight(w) ? ` (+1)` : "";
  return `${DAYS_SHORT[w.day_of_week]} ${w.start_time}–${w.end_time}${next}`;
}

/**
 * Per-day coverage segments [startMin, endMin) for a week strip, splitting
 * windows that run past midnight into the following day.
 */
export function weekSegments(windows: TrackingWindowInput[]): [number, number][][] {
  const days: [number, number][][] = Array.from({ length: 7 }, () => []);
  for (const w of windows) {
    const start = toMinutes(w.start_time);
    const end = toMinutes(w.end_time);
    if (end > start) {
      days[w.day_of_week].push([start, end]);
    } else {
      // Past midnight (or 24h when start === end): today until 24:00, then tomorrow until `end`.
      days[w.day_of_week].push([start, 1440]);
      if (end > 0) days[(w.day_of_week + 1) % 7].push([0, end]);
    }
  }
  return days;
}

/** "5 dk önce" style relative time in Turkish. */
export function relativeTime(iso: string | null, now = Date.now()): string {
  if (!iso) return "—";
  const diff = Math.round((new Date(iso).getTime() - now) / 1000);
  const abs = Math.abs(diff);
  const fmt = new Intl.RelativeTimeFormat("tr-TR", { numeric: "auto" });
  if (abs < 60) return fmt.format(Math.round(diff), "second");
  if (abs < 3600) return fmt.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return fmt.format(Math.round(diff / 3600), "hour");
  return fmt.format(Math.round(diff / 86400), "day");
}

/** Weekday + time in the user's locale, e.g. "Pzt 20:00". */
export function formatDayTime(iso: string, timeZone: string): string {
  const d = new Date(iso);
  const day = new Intl.DateTimeFormat("tr-TR", { weekday: "short", timeZone }).format(d);
  const time = new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone }).format(d);
  return `${day} ${time}`;
}

export const PRESETS: { label: string; windows: () => TrackingWindowInput[] }[] = [
  {
    label: "Her gün 7/24",
    windows: () => Array.from({ length: 7 }, (_, d) => ({ day_of_week: d, start_time: "00:00", end_time: "00:00" })),
  },
  {
    label: "Hafta içi akşam (19:00–01:00)",
    windows: () => Array.from({ length: 5 }, (_, d) => ({ day_of_week: d, start_time: "19:00", end_time: "01:00" })),
  },
  {
    label: "Hafta sonu (12:00–02:00)",
    windows: () => [5, 6].map((d) => ({ day_of_week: d, start_time: "12:00", end_time: "02:00" })),
  },
];
