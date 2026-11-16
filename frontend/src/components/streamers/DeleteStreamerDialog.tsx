import { Loader2 } from "lucide-react";
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
import { ApiError } from "@/services/api";
import type { Streamer } from "@/types/api";

interface Props {
  streamer: Streamer | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: (streamer: Streamer) => Promise<void>;
  onDeactivate: (streamer: Streamer) => Promise<void>;
}

export function DeleteStreamerDialog({ streamer, onOpenChange, onConfirm, onDeactivate }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Keep the last streamer so its name stays visible during the close animation.
  const [shown, setShown] = useState<Streamer | null>(streamer);

  useEffect(() => {
    setError(null);
    if (streamer) setShown(streamer);
  }, [streamer]);

  // Deleting is only possible without recordings; otherwise offer deactivation.
  const blocked = Boolean(shown && shown.recordings_count > 0);

  const run = async (action: (s: Streamer) => Promise<void>) => {
    if (!streamer) return;
    setBusy(true);
    setError(null);
    try {
      await action(streamer);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Beklenmeyen bir hata oluştu.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={Boolean(streamer)} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Yayıncıyı sil</DialogTitle>
          <DialogDescription>
            {blocked ? (
              <>
                <strong className="text-foreground">{shown?.name}</strong> için {shown?.recordings_count} kayıt
                bulunuyor. Kayıtları ve kesitleri korumak için yayıncı silinemez; bunun yerine pasif yapabilirsiniz.
              </>
            ) : (
              <>
                <strong className="text-foreground">{shown?.name}</strong> kalıcı olarak silinecek. Bu işlem geri
                alınamaz.
              </>
            )}
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
          {blocked ? (
            shown?.is_active && (
              <Button onClick={() => run(onDeactivate)} disabled={busy}>
                {busy && <Loader2 className="animate-spin" />}
                Pasif yap
              </Button>
            )
          ) : (
            <Button variant="destructive" onClick={() => run(onConfirm)} disabled={busy}>
              {busy && <Loader2 className="animate-spin" />}
              Kalıcı olarak sil
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
