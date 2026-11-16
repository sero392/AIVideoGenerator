import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  KeyRound,
  Loader2,
  Radio,
  RefreshCw,
  ShieldAlert,
  Signal,
  SignalZero,
  Video,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { ScheduleEditorDialog } from "@/components/schedule/ScheduleEditorDialog";
import { WeekStrip } from "@/components/schedule/WeekStrip";
import { PlatformBadge } from "@/components/streamers/StreamerBadges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiQuery } from "@/hooks/useApiQuery";
import { cn } from "@/lib/utils";
import { ApiError, api } from "@/services/api";
import { useServerEvent } from "@/services/events";
import type { PlatformInfo, TrackedStreamer, TrackingOverview, TrackingWindowInput } from "@/types/api";
import { formatNumber } from "@/utils/format";
import { STATE_META, formatDayTime, formatWindow, relativeTime } from "@/utils/schedule";
import { PLATFORM_LABEL, shortUrl } from "@/utils/streamers";

const WEEKDAY_INDEX: Record<string, number> = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 };

function todayIndex(timeZone: string): number {
  return WEEKDAY_INDEX[new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone }).format(new Date())] ?? 0;
}

export function SchedulePage() {
  const overview = useApiQuery(api.tracking.overview, 30_000);
  const events = useApiQuery((signal) => api.tracking.events(10, signal), 60_000);
  const [editing, setEditing] = useState<TrackedStreamer | null>(null);
  const [checkingId, setCheckingId] = useState<number | null>(null);

  // Backend pushes updates after every tracking cycle that changed something.
  useServerEvent((event) => {
    if (event.type === "tracking.updated" || event.type.startsWith("stream.")) {
      overview.refetch();
      events.refetch();
    }
  });

  const data = overview.data;

  const checkNow = async (s: TrackedStreamer) => {
    setCheckingId(s.id);
    try {
      const result = await api.tracking.checkNow(s.id);
      const meta = STATE_META[result.status.state];
      const state = result.status.state;
      if (state === "error") toast.error(`${s.name}: ${result.status.error_message ?? "Kontrol başarısız."}`);
      else if (state === "not_configured" || state === "unsupported") toast.warning(`${s.name}: ${meta.label}`);
      else toast.success(`${s.name}: ${meta.label}`);
      overview.refetch();
      events.refetch();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Kontrol başarısız.");
    } finally {
      setCheckingId(null);
    }
  };

  const startRecording = async (s: TrackedStreamer) => {
    try {
      await api.recordings.startLive(s.id);
      toast.success(`${s.name} kaydı başladı.`);
      overview.refetch();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Kayıt başlatılamadı.");
    }
  };

  const saveSchedule = async (s: TrackedStreamer, windows: TrackingWindowInput[]) => {
    await api.streamers.putSchedule(s.id, windows);
    toast.success(`${s.name} takvimi kaydedildi.`);
    overview.refetch();
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Yayın Takvimi</h2>
          <p className="text-muted-foreground text-sm">
            {data
              ? `Saat dilimi ${data.timezone} · kontrol turu her ${data.tick_seconds} sn${
                  data.next_cycle_at ? ` · sonraki tur ${relativeTime(data.next_cycle_at)}` : ""
                }`
              : "Yayıncıların hangi saatlerde takip edileceğini belirleyin"}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={overview.refetch} disabled={overview.loading}>
          <RefreshCw className={cn(overview.loading && "animate-spin")} />
          Yenile
        </Button>
      </div>

      {overview.error && !data && (
        <Card className="border-destructive/40 bg-destructive/5 py-4" role="alert">
          <CardContent className="flex items-center gap-3 px-4 text-sm">
            <AlertTriangle className="text-destructive size-5 shrink-0" />
            <div>
              <p className="font-medium">Takip durumu yüklenemedi</p>
              <p className="text-muted-foreground">{overview.error.message}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {data && !data.tracking_enabled && (
        <Card className="border-warning/40 bg-warning/5 py-4" role="status">
          <CardContent className="flex items-center gap-3 px-4 text-sm">
            <AlertTriangle className="text-warning size-5 shrink-0" />
            Otomatik takip kapalı (<code>TRACKING_ENABLED</code> / <code>SCHEDULER_ENABLED</code>). "Şimdi kontrol et"
            yine çalışır.
          </CardContent>
        </Card>
      )}

      <PlatformCards data={data} loading={!data && overview.loading} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section className="min-w-0 space-y-3 lg:col-span-2" aria-label="Yayıncılar">
          {!data && overview.loading ? (
            [0, 1].map((i) => <Skeleton key={i} className="h-40 w-full rounded-xl" />)
          ) : data && data.streamers.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
                <CalendarClock className="text-muted-foreground size-8" />
                <p className="font-medium">Takip edilecek yayıncı yok</p>
                <Button asChild size="sm">
                  <Link to="/streamers">Yayıncı ekle</Link>
                </Button>
              </CardContent>
            </Card>
          ) : (
            data?.streamers.map((s) => (
              <StreamerCard
                key={s.id}
                streamer={s}
                timezone={data.timezone}
                checking={checkingId === s.id}
                onCheck={() => checkNow(s)}
                onEdit={() => setEditing(s)}
                onRecord={() => startRecording(s)}
              />
            ))
          )}
        </section>

        <Card className="h-fit min-w-0">
          <CardHeader>
            <CardTitle>Son Yayın Hareketleri</CardTitle>
            <CardDescription>Canlıya geçiş ve yayın bitişleri</CardDescription>
          </CardHeader>
          <CardContent>
            {events.data && events.data.length > 0 ? (
              <ul className="space-y-3">
                {events.data.map((e) => (
                  <li key={e.id} className="flex items-start gap-3">
                    <div
                      className={cn(
                        "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md",
                        e.event_type === "went_live" ? "bg-destructive/15 text-destructive" : "bg-muted text-muted-foreground",
                      )}
                    >
                      {e.event_type === "went_live" ? <Signal className="size-4" /> : <SignalZero className="size-4" />}
                    </div>
                    <div className="min-w-0 text-sm">
                      <p className="truncate font-medium">
                        {e.streamer_name} {e.event_type === "went_live" ? "canlı yayına başladı" : "yayını bitirdi"}
                      </p>
                      {e.title && <p className="text-muted-foreground truncate text-xs">{e.title}</p>}
                      <p className="text-muted-foreground text-xs">{relativeTime(e.occurred_at)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground py-6 text-center text-sm">Henüz yayın hareketi kaydedilmedi.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <ScheduleEditorDialog
        streamer={editing}
        timezone={data?.timezone ?? ""}
        onOpenChange={(o) => !o && setEditing(null)}
        onSave={saveSchedule}
      />
    </div>
  );
}

function PlatformCards({ data, loading }: { data: TrackingOverview | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
    );
  }
  if (!data) return null;
  const used = new Set(data.streamers.map((s) => s.platform));
  return (
    <section className="grid grid-cols-1 gap-4 sm:grid-cols-3" aria-label="Platform bağlantıları">
      {data.platforms.map((p) => (
        <PlatformCard key={p.platform} info={p} used={used.has(p.platform)} />
      ))}
    </section>
  );
}

function PlatformCard({ info, used }: { info: PlatformInfo; used: boolean }) {
  return (
    <Card className="gap-3 py-4">
      <CardContent className="space-y-2 px-4">
        <div className="flex items-center justify-between gap-2">
          <p className="font-medium">{PLATFORM_LABEL[info.platform]}</p>
          {info.configured ? (
            <Badge variant="success">
              <CheckCircle2 />
              Bağlı
            </Badge>
          ) : (
            <Badge variant={used ? "warning" : "muted"}>
              <KeyRound />
              Anahtar gerekli
            </Badge>
          )}
        </div>
        {info.configured ? (
          <p className="text-muted-foreground text-xs">Her {Math.round(info.poll_interval_seconds / 60)} dakikada bir kontrol</p>
        ) : (
          <p className="text-muted-foreground text-xs">
            <code className="bg-muted rounded px-1">backend/.env</code> dosyasına{" "}
            {info.required_settings.map((s, i) => (
              <span key={s}>
                {i > 0 && " ve "}
                <code className="bg-muted rounded px-1">{s}</code>
              </span>
            ))}{" "}
            ekleyip backend'i yeniden başlatın.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function StreamerCard({
  streamer: s,
  timezone,
  checking,
  onCheck,
  onEdit,
  onRecord,
}: {
  streamer: TrackedStreamer;
  timezone: string;
  checking: boolean;
  onCheck: () => void;
  onEdit: () => void;
  onRecord: () => void;
}) {
  const meta = STATE_META[s.status.state];
  const live = s.status.state === "live";

  let scheduleText: string;
  if (!s.windows.length) scheduleText = "Takvim yok — otomatik kontrol edilmez";
  else if (s.in_schedule) scheduleText = s.next_change_at ? `Takipte · ${formatDayTime(s.next_change_at, timezone)}'e kadar` : "Takipte";
  else scheduleText = s.next_change_at ? `Sonraki takip: ${formatDayTime(s.next_change_at, timezone)}` : "Takvim dışı";

  return (
    <Card className={cn("gap-4 py-4", live && "border-destructive/40", !s.is_active && "opacity-60")} data-testid={`tracked-${s.id}`}>
      <CardContent className="space-y-4 px-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate font-medium">{s.name}</p>
              <PlatformBadge platform={s.platform} />
            </div>
            <a
              href={s.channel_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs"
            >
              {shortUrl(s.channel_url)}
              <ExternalLink className="size-3" />
            </a>
          </div>
          <Badge variant={meta.variant} className={cn(live && "animate-pulse")}>
            {live && <Radio />}
            {meta.label}
          </Badge>
        </div>

        {live && (
          <div className="bg-destructive/5 border-destructive/20 rounded-lg border px-3 py-2 text-sm">
            <p className="truncate font-medium">{s.status.title ?? "Başlıksız yayın"}</p>
            <p className="text-muted-foreground text-xs">
              {s.status.live_started_at && `${relativeTime(s.status.live_started_at)} başladı`}
              {s.status.viewer_count != null && ` · ${formatNumber(s.status.viewer_count)} izleyici`}
              {s.status.stream_url && (
                <>
                  {" · "}
                  <a href={s.status.stream_url} target="_blank" rel="noopener noreferrer" className="text-foreground underline">
                    Yayını aç
                  </a>
                </>
              )}
            </p>
          </div>
        )}
        {s.status.state === "error" && s.status.error_message && (
          <p className="text-destructive text-xs" role="alert">
            {s.status.error_message}
          </p>
        )}
        {live && !s.recording_permission_confirmed && (
          <p className="text-warning flex items-center gap-1.5 text-xs">
            <ShieldAlert className="size-3.5" />
            Kayıt izni onaylanmadığı için bu yayın kaydedilmeyecek.
          </p>
        )}
        {s.active_recording_id != null ? (
          <Link to="/recordings" className="text-destructive inline-flex items-center gap-1.5 text-xs font-medium">
            <span className="bg-destructive size-2 animate-pulse rounded-full" />
            Kaydediliyor — Kayıtlar sayfasında görüntüle
          </Link>
        ) : (
          live &&
          s.recording_permission_confirmed &&
          (s.live_capture_enabled ? (
            <Button variant="outline" size="sm" onClick={onRecord}>
              <Video />
              Kaydı başlat
            </Button>
          ) : (
            <p className="text-muted-foreground text-xs">
              Canlı kayıt bu yayıncı için kapalı (Yayıncı Yönetimi → düzenle). Yayıncının kendi kaydını Kayıtlar sayfasından
              da yükleyebilirsiniz.
            </p>
          ))
        )}

        <WeekStrip windows={s.windows} today={todayIndex(timezone)} />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-muted-foreground min-w-0 text-xs">
            <p>{scheduleText}</p>
            <p>
              Son kontrol: {relativeTime(s.status.checked_at)}
              {s.windows.length > 0 && s.windows.length <= 3 && ` · ${s.windows.map(formatWindow).join(", ")}`}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={onEdit}>
              <CalendarClock />
              Takvimi düzenle
            </Button>
            <Button variant="secondary" size="sm" onClick={onCheck} disabled={checking}>
              {checking ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              Şimdi kontrol et
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
