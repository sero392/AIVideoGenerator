import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ComponentState, SystemStatus } from "@/types/api";

const COMPONENT_LABEL: Record<string, string> = {
  database: "Veritabanı",
  ollama: "Ollama (Qwen)",
  "faster-whisper": "faster-whisper",
  ffmpeg: "FFmpeg",
  opencv: "OpenCV",
  scheduler: "Zamanlayıcı",
  youtube: "YouTube OAuth",
};

const STATE: Record<ComponentState, { text: string; variant: "success" | "warning" | "destructive" | "muted" }> = {
  ok: { text: "Çalışıyor", variant: "success" },
  unavailable: { text: "Hazır değil", variant: "warning" },
  disabled: { text: "Kapalı", variant: "muted" },
  error: { text: "Hata", variant: "destructive" },
};

const OVERALL = {
  ok: { text: "Tüm sistemler çalışıyor", variant: "success" },
  degraded: { text: "Kısmi hazır", variant: "warning" },
  error: { text: "Sorun var", variant: "destructive" },
} as const;

interface Props {
  status: SystemStatus | null;
  loading: boolean;
}

export function SystemStatusCard({ status, loading }: Props) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Sistem Durumu</CardTitle>
        <CardDescription>Bileşenlerin anlık kontrolü</CardDescription>
        {status && (
          <CardAction>
            <Badge variant={OVERALL[status.overall].variant}>{OVERALL[status.overall].text}</Badge>
          </CardAction>
        )}
      </CardHeader>
      <CardContent>
        {loading && !status ? (
          <div className="space-y-3">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : status ? (
          <ul className="space-y-1">
            {status.components.map((c) => {
              const s = STATE[c.status];
              return (
                <li key={c.name} className="hover:bg-muted/40 flex items-center gap-3 rounded-md px-2 py-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{COMPONENT_LABEL[c.name] ?? c.name}</p>
                    {c.detail && <p className="text-muted-foreground truncate text-xs" title={c.detail}>{c.detail}</p>}
                  </div>
                  <Badge variant={s.variant}>{s.text}</Badge>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-muted-foreground text-sm">Durum bilgisi alınamadı.</p>
        )}
      </CardContent>
    </Card>
  );
}
