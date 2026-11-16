import { ShieldAlert, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Streamer } from "@/types/api";
import { formatDateTime } from "@/utils/format";
import { PLATFORM_CLASS, PLATFORM_LABEL } from "@/utils/streamers";

export function PlatformBadge({ platform }: { platform: Streamer["platform"] }) {
  return (
    <Badge variant="outline" className={cn(PLATFORM_CLASS[platform])}>
      {PLATFORM_LABEL[platform]}
    </Badge>
  );
}

export function PermissionBadge({ streamer }: { streamer: Streamer }) {
  if (streamer.recording_permission_confirmed) {
    const title = [
      streamer.permission_confirmed_at && `Onay: ${formatDateTime(streamer.permission_confirmed_at)}`,
      streamer.permission_notes,
    ]
      .filter(Boolean)
      .join("\n");
    return (
      <Badge variant="success" title={title}>
        <ShieldCheck />
        İzin onaylı
      </Badge>
    );
  }
  return (
    <Badge variant="warning" title="İzin onaylanmadan kayıt yapılmaz">
      <ShieldAlert />
      İzin yok
    </Badge>
  );
}
