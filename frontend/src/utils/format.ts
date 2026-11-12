const numberFmt = new Intl.NumberFormat("tr-TR");
const dateTimeFmt = new Intl.DateTimeFormat("tr-TR", { dateStyle: "short", timeStyle: "short" });

export function formatNumber(value: number): string {
  return numberFmt.format(value);
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFmt.format(date);
}
