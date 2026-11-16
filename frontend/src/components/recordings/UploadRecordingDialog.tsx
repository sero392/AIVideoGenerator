import { FileVideo, Loader2, Upload } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

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
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { ApiError, api } from "@/services/api";
import type { Recording, Streamer } from "@/types/api";
import { formatBytes } from "@/utils/format";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  streamers: Streamer[];
  allowedExtensions: string[];
  maxUploadGb: number;
  onUploaded: (recording: Recording) => void;
}

export function UploadRecordingDialog({ open, onOpenChange, streamers, allowedExtensions, maxUploadGb, onUploaded }: Props) {
  const permitted = streamers.filter((s) => s.recording_permission_confirmed);
  const [streamerId, setStreamerId] = useState<string>("");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const id = useId();
  const busy = progress !== null;

  useEffect(() => {
    if (open) {
      setStreamerId(permitted.length === 1 ? String(permitted[0].id) : "");
      setTitle("");
      setFile(null);
      setProgress(null);
      setError(null);
    }
  }, [open]);

  const submit = async () => {
    if (!streamerId) return setError("Yayıncı seçin.");
    if (!file) return setError("Bir video dosyası seçin.");
    const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!allowedExtensions.includes(ext)) return setError(`Desteklenmeyen dosya türü. İzin verilenler: ${allowedExtensions.join(", ")}`);
    if (file.size > maxUploadGb * 1024 ** 3) return setError(`Dosya en fazla ${maxUploadGb} GB olabilir.`);

    setError(null);
    setProgress(0);
    abortRef.current = new AbortController();
    try {
      const recording = await api.recordings.upload(
        { streamerId: Number(streamerId), file, title: title.trim() || undefined },
        setProgress,
        abortRef.current.signal,
      );
      onUploaded(recording);
      onOpenChange(false);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof ApiError ? err.message : "Yükleme başarısız.");
    } finally {
      setProgress(null);
    }
  };

  const close = (next: boolean) => {
    if (!next && busy) abortRef.current?.abort();
    onOpenChange(next);
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Kayıt dosyası yükle</DialogTitle>
          <DialogDescription>
            Yayıncının size verdiği kaydı yükleyin (ör. kendi YouTube Studio hesabından indirdiği yayın). Dosya MP4'e
            dönüştürülür; yeniden kodlama yapılmaz, kalite kaybı olmaz.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor={`${id}-streamer`}>Yayıncı</Label>
            <NativeSelect id={`${id}-streamer`} value={streamerId} onChange={(e) => setStreamerId(e.target.value)} disabled={busy}>
              <option value="">Seçin…</option>
              {streamers.map((s) => (
                <option key={s.id} value={s.id} disabled={!s.recording_permission_confirmed}>
                  {s.name}
                  {!s.recording_permission_confirmed && " (izin onaylanmamış)"}
                </option>
              ))}
            </NativeSelect>
            {permitted.length === 0 && (
              <p className="text-warning text-xs">Kayıt izni onaylanmış yayıncı yok; önce Yayıncı Yönetimi'nden izni onaylayın.</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${id}-title`}>Başlık (isteğe bağlı)</Label>
            <Input
              id={`${id}-title`}
              value={title}
              maxLength={300}
              placeholder="Boş bırakılırsa dosya adı kullanılır"
              onChange={(e) => setTitle(e.target.value)}
              disabled={busy}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${id}-file`}>Video dosyası</Label>
            <label
              htmlFor={`${id}-file`}
              className="hover:bg-muted/40 flex cursor-pointer items-center gap-3 rounded-lg border border-dashed px-3 py-4 text-sm"
            >
              <FileVideo className="text-muted-foreground size-5 shrink-0" />
              {file ? (
                <span className="min-w-0 truncate">
                  {file.name} <span className="text-muted-foreground">· {formatBytes(file.size)}</span>
                </span>
              ) : (
                <span className="text-muted-foreground">
                  Dosya seçin ({allowedExtensions.join(", ")} · en fazla {maxUploadGb} GB)
                </span>
              )}
            </label>
            <input
              id={`${id}-file`}
              type="file"
              className="sr-only"
              accept={allowedExtensions.join(",")}
              disabled={busy}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          {progress !== null && (
            <div className="space-y-1" aria-live="polite">
              <div className="bg-muted h-2 overflow-hidden rounded-full">
                <div className="bg-primary h-full transition-[width]" style={{ width: `${Math.round(progress * 100)}%` }} />
              </div>
              <p className="text-muted-foreground text-xs">
                {progress < 1 ? `Yükleniyor… %${Math.round(progress * 100)}` : "Dosya işleniyor (FFmpeg)…"}
              </p>
            </div>
          )}
          {error && (
            <p className="border-destructive/40 bg-destructive/10 text-destructive rounded-md border px-3 py-2 text-sm" role="alert">
              {error}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)}>
            {busy ? "Yüklemeyi iptal et" : "Vazgeç"}
          </Button>
          <Button onClick={submit} disabled={busy || permitted.length === 0}>
            {busy ? <Loader2 className="animate-spin" /> : <Upload />}
            Yükle
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
