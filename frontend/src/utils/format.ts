const numberFmt = new Intl.NumberFormat("tr-TR");
const dateTimeFmt = new Intl.DateTimeFormat("tr-TR", { dateStyle: "short", timeStyle: "short" });

export function formatNumber(value: number): string {
  return numberFmt.format(value);
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFmt.format(date);
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  return `${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: unit >= 2 ? 1 : 0 }).format(value)} ${units[unit]}`;
}

/** 3725 -> "1:02:05", 65 -> "1:05" */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}
