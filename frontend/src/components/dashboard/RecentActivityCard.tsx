import { Activity, Film, Radio, Scissors, SquarePlay } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ActivityItem } from "@/types/api";
import { formatDateTime } from "@/utils/format";

const KIND_ICON = { recording: Film, clip: Scissors, youtube: SquarePlay, stream: Radio } as const;

interface Props {
  items: ActivityItem[] | null;
  loading: boolean;
}

export function RecentActivityCard({ items, loading }: Props) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Son İşlemler</CardTitle>
        <CardDescription>Kayıt, kesit ve YouTube işlemlerinin son hareketleri</CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        {loading && !items ? (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : !items || items.length === 0 ? (
          <div className="flex h-full min-h-48 flex-col items-center justify-center gap-3 rounded-lg border border-dashed text-center">
            <div className="bg-muted text-muted-foreground flex size-10 items-center justify-center rounded-full">
              <Activity className="size-5" />
            </div>
            <div>
              <p className="text-sm font-medium">Henüz işlem yok</p>
              <p className="text-muted-foreground mt-1 max-w-xs text-xs">
                Yayıncı eklenip kayıt alındığında işlemler burada listelenecek.
              </p>
            </div>
          </div>
        ) : (
          <ul className="divide-y">
            {items.map((item, idx) => {
              const Icon = KIND_ICON[item.kind];
              return (
                <li key={`${item.kind}-${idx}`} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-md">
                    <Icon className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{item.title}</p>
                    <p className="text-muted-foreground text-xs">{formatDateTime(item.timestamp)}</p>
                  </div>
                  <Badge variant="muted">{item.status}</Badge>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
