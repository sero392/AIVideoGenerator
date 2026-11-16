import {
  AlertTriangle,
  CircleStop,
  Film,
  FolderInput,
  HardDrive,
  Loader2,
  Play,
  RefreshCw,
  Trash2,
  Upload,
  Wrench,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { DeleteRecordingDialog, VideoPlayerDialog } from "@/components/recordings/RecordingDialogs";
import { UploadRecordingDialog } from "@/components/recordings/UploadRecordingDialog";
import { PlatformBadge } from "@/components/streamers/StreamerBadges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApiQuery } from "@/hooks/useApiQuery";
import { cn } from "@/lib/utils";
import { ApiError, api } from "@/services/api";
import { useServerEvent } from "@/services/events";
import type { Recording, RecordingSource, RecordingStatus, RecordingSystemInfo } from "@/types/api";
import { formatBytes, formatDateTime, formatDuration } from "@/utils/format";

const PAGE_SIZE = 25;

export const RECORDING_STATUS: Record<RecordingStatus, { label: string; variant: "success" | "warning" | "destructive" | "muted" | "secondary" }> = {
  recording: { label: "Kaydediliyor", variant: "destructive" },
  processing: { label: "İşleniyor", variant: "warning" },
  completed: { label: "Tamamlandı", variant: "success" },
  failed: { label: "Başarısız", variant: "destructive" },
  cancelled: { label: "İptal", variant: "muted" },
  scheduled: { label: "Planlandı", variant: "muted" },
};

const SOURCE_LABEL: Record<RecordingSource, string> = { live_capture: "Canlı kayıt", import: "İçe aktarma" };

function useNow(intervalMs: number, enabled: boolean): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, enabled]);
  return now;
}

export function RecordingsPage() {
  const [streamerId, setStreamerId] = useState<string>("all");
  const [status, setStatus] = useState<RecordingStatus | "all">("all");
  const [source, setSource] = useState<RecordingSource | "all">("all");
  const [page, setPage] = useState(0);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [playing, setPlaying] = useState<Recording | null>(null);
  const [deleting, setDeleting] = useState<Recording | null>(null);
  const [stoppingId, setStoppingId] = useState<number | null>(null);
  const [scanning, setScanning] = useState(false);

  const filters = {
    streamer_id: streamerId === "all" ? undefined : Number(streamerId),
    status: status === "all" ? undefined : status,
    source: source === "all" ? undefined : source,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  };
  const list = useApiQuery((signal) => api.recordings.list(filters, signal), { deps: [filters] });
  const active = useApiQuery((signal) => api.recordings.list({ status: "recording", limit: 10 }, signal), { pollMs: 5000 });
  const system = useApiQuery(api.recordings.system, 30_000);
  const streamers = useApiQuery((signal) => api.streamers.list({ limit: 100 }, signal));

  const refreshAll = () => {
    list.refetch();
    active.refetch();
    system.refetch();
  };
  useServerEvent((event) => {
    if (event.type.startsWith("recording.")) refreshAll();
  });

  const activeItems = active.data?.items ?? [];
  const now = useNow(1000, activeItems.length > 0);

  const stop = async (r: Recording) => {
    setStoppingId(r.id);
    try {
      await api.recordings.stop(r.id);
      toast.success(`${r.streamer_name} kaydı durduruldu; dosya hazırlanıyor.`);
      refreshAll();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Kayıt durdurulamadı.");
    } finally {
      setStoppingId(null);
    }
  };

  const scanInbox = async () => {
    setScanning(true);
    try {
      const result = await api.recordings.scanInbox();
      if (result.imported.length) toast.success(`${result.imported.length} dosya içe aktarıldı.`);
      if (result.errors.length)
        toast.error(`${result.errors.length} dosya aktarılamadı`, {
          description: result.errors.map((e) => `${e.file}: ${e.message}`).join("\n"),
        });
      if (!result.imported.length && !result.errors.length)
        toast(`Gelen kutusu boş`, { description: `Dosyaları ${result.inbox_path}/<yayıncı no>/ klasörüne koyun.` });
      refreshAll();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Gelen kutusu taranamadı.");
    } finally {
      setScanning(false);
    }
  };

  const items = list.data?.items ?? [];
  const total = list.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters = streamerId !== "all" || status !== "all" || source !== "all";

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Kayıtlar</h2>
          <p className="text-muted-foreground text-sm">
            {list.data ? `${total} kayıt${hasFilters ? " (filtreli)" : ""}` : "Canlı kayıtlar ve içe aktarılan yayın dosyaları"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={scanInbox} disabled={scanning} title="storage/recordings/inbox/<yayıncı no>/ klasöründeki dosyaları ekle">
            {scanning ? <Loader2 className="animate-spin" /> : <FolderInput />}
            Gelen kutusunu tara
          </Button>
          <Button onClick={() => setUploadOpen(true)}>
            <Upload />
            Dosya yükle
          </Button>
        </div>
      </div>

      <SystemStrip info={system.data} />

      {activeItems.length > 0 && (
        <Card className="border-destructive/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="bg-destructive size-2 animate-pulse rounded-full" />
              Devam eden kayıtlar
            </CardTitle>
            <CardDescription>Yayın bitince kayıt kendiliğinden tamamlanır.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeItems.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center gap-3 rounded-lg border px-3 py-3" data-testid={`active-${r.id}`}>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{r.streamer_name}</p>
                  <p className="text-muted-foreground truncate text-xs">{r.title ?? "Başlıksız yayın"}</p>
                </div>
                <div className="text-right text-sm tabular-nums">
                  <p>{r.started_at ? formatDuration((now - new Date(r.started_at).getTime()) / 1000) : "—"}</p>
                  <p className="text-muted-foreground text-xs">{formatBytes(r.file_size_bytes)}</p>
                </div>
                <Button variant="outline" size="sm" onClick={() => stop(r)} disabled={stoppingId === r.id}>
                  {stoppingId === r.id ? <Loader2 className="animate-spin" /> : <CircleStop />}
                  Durdur
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card className="gap-0 py-0">
        <div className="grid grid-cols-1 gap-3 border-b p-4 sm:grid-cols-3">
          <NativeSelect aria-label="Yayıncı filtresi" value={streamerId} onChange={(e) => { setStreamerId(e.target.value); setPage(0); }}>
            <option value="all">Tüm yayıncılar</option>
            {streamers.data?.items.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect aria-label="Durum filtresi" value={status} onChange={(e) => { setStatus(e.target.value as RecordingStatus | "all"); setPage(0); }}>
            <option value="all">Tüm durumlar</option>
            {(["completed", "recording", "processing", "failed"] as const).map((s) => (
              <option key={s} value={s}>
                {RECORDING_STATUS[s].label}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect aria-label="Kaynak filtresi" value={source} onChange={(e) => { setSource(e.target.value as RecordingSource | "all"); setPage(0); }}>
            <option value="all">Tüm kaynaklar</option>
            <option value="import">İçe aktarma</option>
            <option value="live_capture">Canlı kayıt</option>
          </NativeSelect>
        </div>

        {list.error ? (
          <div className="flex items-center gap-3 p-6 text-sm" role="alert">
            <AlertTriangle className="text-destructive size-5 shrink-0" />
            <span>{list.error.message}</span>
            <Button variant="outline" size="sm" className="ml-auto" onClick={list.refetch}>
              <RefreshCw />
              Tekrar dene
            </Button>
          </div>
        ) : !list.data ? (
          <div className="space-y-3 p-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <div className="bg-muted text-muted-foreground flex size-12 items-center justify-center rounded-full">
              <Film className="size-6" />
            </div>
            <p className="font-medium">{hasFilters ? "Filtreyle eşleşen kayıt yok" : "Henüz kayıt yok"}</p>
            {!hasFilters && (
              <p className="text-muted-foreground max-w-md text-sm">
                Yayıncının verdiği bir dosyayı yükleyin ya da Yayıncı Yönetimi'nden bir yayıncı için "Canlı yayını otomatik
                kaydet" seçeneğini açın.
              </p>
            )}
          </CardContent>
        ) : (
          <>
            <div className="hidden xl:block">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="pl-4">Kayıt</TableHead>
                    <TableHead>Kaynak</TableHead>
                    <TableHead>Durum</TableHead>
                    <TableHead>Tarih</TableHead>
                    <TableHead className="text-right">Süre</TableHead>
                    <TableHead className="text-right">Boyut</TableHead>
                    <TableHead className="pr-4 text-right">
                      <span className="sr-only">İşlemler</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((r) => (
                    <TableRow key={r.id} data-testid={`recording-row-${r.id}`}>
                      <TableCell className="max-w-80 pl-4 whitespace-normal">
                        <p className="truncate font-medium">{r.title ?? "Başlıksız"}</p>
                        <div className="text-muted-foreground flex items-center gap-2 text-xs">
                          <span className="truncate">{r.streamer_name}</span>
                          <PlatformBadge platform={r.platform} />
                        </div>
                        {r.error_message && (
                          <p className={cn("mt-1 text-xs", r.status === "failed" ? "text-destructive" : "text-muted-foreground")}>
                            {r.error_message}
                          </p>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{SOURCE_LABEL[r.source]}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={RECORDING_STATUS[r.status].variant}>{RECORDING_STATUS[r.status].label}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{formatDateTime(r.started_at ?? r.created_at)}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatDuration(r.duration_seconds)}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatBytes(r.file_size_bytes)}</TableCell>
                      <TableCell className="pr-4 text-right">
                        <RowActions recording={r} onPlay={setPlaying} onDelete={setDeleting} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <ul className="divide-y xl:hidden">
              {items.map((r) => (
                <li key={r.id} className="space-y-2 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{r.title ?? "Başlıksız"}</p>
                      <p className="text-muted-foreground text-xs">
                        {r.streamer_name} · {formatDateTime(r.started_at ?? r.created_at)}
                      </p>
                    </div>
                    <Badge variant={RECORDING_STATUS[r.status].variant}>{RECORDING_STATUS[r.status].label}</Badge>
                  </div>
                  {r.error_message && <p className="text-muted-foreground text-xs">{r.error_message}</p>}
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant="outline">{SOURCE_LABEL[r.source]}</Badge>
                    <span className="text-muted-foreground tabular-nums">
                      {formatDuration(r.duration_seconds)} · {formatBytes(r.file_size_bytes)}
                    </span>
                    <div className="ml-auto">
                      <RowActions recording={r} onPlay={setPlaying} onDelete={setDeleting} />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            {pageCount > 1 && (
              <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
                <span className="text-muted-foreground">
                  Sayfa {page + 1} / {pageCount}
                </span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>
                    Önceki
                  </Button>
                  <Button variant="outline" size="sm" disabled={page + 1 >= pageCount} onClick={() => setPage(page + 1)}>
                    Sonraki
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      <UploadRecordingDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        streamers={streamers.data?.items ?? []}
        allowedExtensions={system.data?.allowed_extensions ?? [".mp4", ".mkv", ".mov", ".webm", ".ts", ".flv", ".m4v"]}
        maxUploadGb={system.data?.max_upload_gb ?? 20}
        onUploaded={(r) => {
          toast.success(`"${r.title ?? "Kayıt"}" içe aktarıldı.`);
          refreshAll();
        }}
      />
      <VideoPlayerDialog recording={playing} onOpenChange={(o) => !o && setPlaying(null)} />
      <DeleteRecordingDialog
        recording={deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        onDeleted={(r) => {
          toast.success(`"${r.title ?? "Kayıt"}" silindi.`);
          if (items.length === 1 && page > 0) setPage(page - 1);
          else refreshAll();
        }}
      />
    </div>
  );
}

function RowActions({
  recording: r,
  onPlay,
  onDelete,
}: {
  recording: Recording;
  onPlay: (r: Recording) => void;
  onDelete: (r: Recording) => void;
}) {
  const busy = r.status === "recording" || r.status === "processing";
  return (
    <div className="inline-flex gap-1">
      <Button variant="ghost" size="icon" aria-label={`${r.title ?? "Kayıt"} izle`} disabled={!r.file_available} onClick={() => onPlay(r)}>
        <Play />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`${r.title ?? "Kayıt"} sil`}
        className="hover:text-destructive"
        disabled={busy}
        onClick={() => onDelete(r)}
      >
        <Trash2 />
      </Button>
    </div>
  );
}

function SystemStrip({ info }: { info: RecordingSystemInfo | null }) {
  if (!info) return <Skeleton className="h-14 w-full rounded-xl" />;
  const lowDisk = info.free_gb < info.min_free_gb;
  return (
    <Card className="py-3">
      <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 text-sm">
        <span className="flex items-center gap-2">
          <Wrench className="text-muted-foreground size-4" />
          FFmpeg:
          <Badge variant={info.ffmpeg_available ? "success" : "destructive"}>
            {info.ffmpeg_available ? (info.ffmpeg_source === "bundled" ? "Hazır (proje içi)" : "Hazır (sistem)") : "Yok"}
          </Badge>
        </span>
        <span className="flex items-center gap-2">
          Canlı kayıt aracı:
          <Badge variant={info.ytdlp_version ? "secondary" : "muted"}>{info.ytdlp_version ? `yt-dlp ${info.ytdlp_version}` : "Kurulu değil"}</Badge>
        </span>
        <span className={cn("flex items-center gap-2", lowDisk && "text-destructive")}>
          <HardDrive className="size-4" />
          {info.free_gb.toLocaleString("tr-TR")} GB boş
          {lowDisk && ` (en az ${info.min_free_gb} GB gerekli; canlı kayıt başlamaz)`}
        </span>
        <span className="text-muted-foreground">
          Aktif: {info.active_count}/{info.max_concurrent} · en uzun {info.max_hours} saat
        </span>
      </CardContent>
    </Card>
  );
}
