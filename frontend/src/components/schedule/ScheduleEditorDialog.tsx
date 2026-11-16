import { Loader2, Moon, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { WeekStrip } from "@/components/schedule/WeekStrip";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { ApiError } from "@/services/api";
import type { TrackedStreamer, TrackingWindowInput } from "@/types/api";
import { DAYS_LONG, PRESETS, crossesMidnight, isValidTime } from "@/utils/schedule";

const MAX_WINDOWS = 28;

interface Props {
  streamer: TrackedStreamer | null;
  timezone: string;
  onOpenChange: (open: boolean) => void;
  onSave: (streamer: TrackedStreamer, windows: TrackingWindowInput[]) => Promise<void>;
}

/** Client-side check mirroring the backend rules; returns a message or null. */
export function validateWindows(windows: TrackingWindowInput[]): string | null {
  if (windows.length > MAX_WINDOWS) return `En fazla ${MAX_WINDOWS} zaman aralığı eklenebilir.`;
  for (const w of windows) {
    if (!isValidTime(w.start_time) || !isValidTime(w.end_time)) return "Saatler SS:DD biçiminde olmalıdır.";
  }
  const keys = windows.map((w) => `${w.day_of_week}-${w.start_time}-${w.end_time}`);
  if (new Set(keys).size !== keys.length) return "Aynı gün ve saat aralığı birden fazla kez eklenmiş.";
  return null;
}

export function ScheduleEditorDialog({ streamer, timezone, onOpenChange, onSave }: Props) {
  const [rows, setRows] = useState<TrackingWindowInput[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (streamer) {
      setRows(streamer.windows.map(({ day_of_week, start_time, end_time }) => ({ day_of_week, start_time, end_time })));
      setError(null);
    }
  }, [streamer]);

  const update = (index: number, patch: Partial<TrackingWindowInput>) => {
    setRows((r) => r.map((row, i) => (i === index ? { ...row, ...patch } : row)));
    setError(null);
  };

  const addRow = () => {
    const last = rows.at(-1);
    setRows((r) => [
      ...r,
      last
        ? { ...last, day_of_week: (last.day_of_week + 1) % 7 }
        : { day_of_week: 0, start_time: "20:00", end_time: "23:00" },
    ]);
    setError(null);
  };

  const save = async () => {
    if (!streamer) return;
    const problem = validateWindows(rows);
    if (problem) {
      setError(problem);
      return;
    }
    setSaving(true);
    try {
      await onSave(streamer, rows);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Takvim kaydedilemedi.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={Boolean(streamer)} onOpenChange={(o) => !saving && onOpenChange(o)}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Takip takvimi — {streamer?.name}</DialogTitle>
          <DialogDescription>
            Yayıncı yalnızca bu saatlerde kontrol edilir. Saatler {timezone} saat dilimindedir. Bitiş saati
            başlangıçtan küçükse aralık gece yarısını geçer; ikisi eşitse 24 saat takip edilir.
          </DialogDescription>
        </DialogHeader>

        <WeekStrip windows={rows} />

        <div className="flex flex-wrap gap-2">
          {PRESETS.map((preset) => (
            <Button
              key={preset.label}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setRows(preset.windows());
                setError(null);
              }}
            >
              {preset.label}
            </Button>
          ))}
          <Button type="button" variant="ghost" size="sm" onClick={() => setRows([])} disabled={!rows.length}>
            Temizle
          </Button>
        </div>

        <div className="space-y-2">
          {rows.length === 0 && (
            <p className="text-muted-foreground rounded-lg border border-dashed px-3 py-6 text-center text-sm">
              Zaman aralığı yok — bu yayıncı otomatik olarak kontrol edilmez.
            </p>
          )}
          {rows.map((row, index) => (
            <div key={index} className="grid grid-cols-[1fr_auto] items-center gap-2 sm:grid-cols-[9rem_1fr_auto]">
              <NativeSelect
                aria-label={`${index + 1}. aralık günü`}
                value={row.day_of_week}
                onChange={(e) => update(index, { day_of_week: Number(e.target.value) })}
                className="col-span-2 sm:col-span-1"
              >
                {DAYS_LONG.map((day, d) => (
                  <option key={d} value={d}>
                    {day}
                  </option>
                ))}
              </NativeSelect>
              <div className="flex items-center gap-2">
                <Input
                  type="time"
                  aria-label={`${index + 1}. aralık başlangıç`}
                  value={row.start_time}
                  onChange={(e) => update(index, { start_time: e.target.value })}
                  className="min-w-0"
                />
                <span className="text-muted-foreground">–</span>
                <Input
                  type="time"
                  aria-label={`${index + 1}. aralık bitiş`}
                  value={row.end_time}
                  onChange={(e) => update(index, { end_time: e.target.value })}
                  className="min-w-0"
                />
                {isValidTime(row.start_time) && isValidTime(row.end_time) && crossesMidnight(row) && (
                  <span
                    className="text-muted-foreground shrink-0"
                    title={row.start_time === row.end_time ? "24 saat" : "Gece yarısını geçer"}
                  >
                    <Moon className="size-4" />
                  </span>
                )}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`${index + 1}. aralığı sil`}
                onClick={() => setRows((r) => r.filter((_, i) => i !== index))}
              >
                <Trash2 />
              </Button>
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={addRow} disabled={rows.length >= MAX_WINDOWS}>
            <Plus />
            Aralık ekle
          </Button>
        </div>

        {error && (
          <p className="border-destructive/40 bg-destructive/10 text-destructive rounded-md border px-3 py-2 text-sm" role="alert">
            {error}
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            Vazgeç
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving && <Loader2 className="animate-spin" />}
            Takvimi kaydet
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
