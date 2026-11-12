import { Menu } from "lucide-react";
import { useLocation } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApiQuery } from "@/hooks/useApiQuery";
import type { SocketState } from "@/hooks/useEventSocket";
import { api } from "@/services/api";

import { NAV_ITEMS } from "./navigation";

interface HeaderProps {
  onMenuClick: () => void;
  socketState: SocketState;
}

const SOCKET_LABEL: Record<SocketState, { text: string; variant: "success" | "warning" | "destructive" }> = {
  open: { text: "Canlı bağlantı", variant: "success" },
  connecting: { text: "Bağlanıyor…", variant: "warning" },
  closed: { text: "Bağlantı yok", variant: "destructive" },
};

export function Header({ onMenuClick, socketState }: HeaderProps) {
  const { pathname } = useLocation();
  const current = NAV_ITEMS.find((item) => (item.path === "/" ? pathname === "/" : pathname.startsWith(item.path)));
  const health = useApiQuery(api.health, 30_000);
  const socket = SOCKET_LABEL[socketState];

  return (
    <header className="bg-background/80 sticky top-0 z-20 flex h-16 items-center gap-3 border-b px-4 backdrop-blur md:px-8">
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenuClick} aria-label="Menüyü aç">
        <Menu />
      </Button>
      <h1 className="truncate text-base font-semibold tracking-tight md:text-lg">{current?.label ?? "Sayfa bulunamadı"}</h1>

      <div className="ml-auto flex items-center gap-2">
        <Badge variant={socket.variant} className="hidden sm:inline-flex">
          <span className="size-1.5 rounded-full bg-current" />
          {socket.text}
        </Badge>
        {health.data ? (
          <Badge variant="muted">API v{health.data.version}</Badge>
        ) : (
          <Badge variant={health.error ? "destructive" : "muted"}>{health.error ? "API çevrimdışı" : "API…"}</Badge>
        )}
      </div>
    </header>
  );
}
