import { Download, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, api } from "@/services/api";
import type { Recording } from "@/types/api";
import { formatBytes, formatDuration } from "@/utils/format";

export function VideoPlayerDialog({ recording, onOpenChange }: { recording: Recording | null; onOpenChange: (o: boolean) => void }) {
  return (
    <Dialog open={Boolean(recording)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="truncate">{recording?.title ?? "Kayıt"}</DialogTitle>
          <DialogDescription>
            {recording?.streamer_name} · {formatDuration(recording?.duration_seconds)} · {formatBytes(recording?.file_size_bytes)}
          </DialogDescription>
        </DialogHeader>
        {recording && (
          <video
            key={recording.id}
            src={api.recordings.fileUrl(recording.id)}
            controls
            preload="metadata"
            className="max-h-[70svh] w-full rounded-lg bg-black"
          />
        )}
        <DialogFooter>
          {recording && (
            <Button variant="outline" asChild>
              <a href={api.recordings.fileUrl(recording.id)} download>
                <Download />
                İndir
              </a>
            </Button>
          )}
          <Button onClick={() => onOpenChange(false)}>Kapat</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function DeleteRecordingDialog({
  recording,
  onOpenChange,
  onDeleted,
}: {
  recording: Recording | null;
  onOpenChange: (o: boolean) => void;
  onDeleted: (r: Recording) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shown, setShown] = useState<Recording | null>(recording);
  useEffect(() => {
    setError(null);
    if (recording) setShown(recording);
  }, [recording]);

  const confirm = async () => {
    if (!recording) return;
    setBusy(true);
    try {
      await api.recordings.remove(recording.id);
      onDeleted(recording);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Kayıt silinemedi.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={Boolean(recording)} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Kaydı sil</DialogTitle>
          <DialogDescription>
            <strong className="text-foreground">{shown?.title ?? "Bu kayıt"}</strong> ve video dosyası (
            {formatBytes(shown?.file_size_bytes)}) diskten kalıcı olarak silinecek. Bu işlem geri alınamaz.
          </DialogDescription>
        </DialogHeader>
        {error && (
          <p className="border-destructive/40 bg-destructive/10 text-destructive rounded-md border px-3 py-2 text-sm" role="alert">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Vazgeç
          </Button>
          <Button variant="destructive" onClick={confirm} disabled={busy}>
            {busy && <Loader2 className="animate-spin" />}
            Kalıcı olarak sil
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
