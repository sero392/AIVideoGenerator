import { useState } from "react";
import { Outlet } from "react-router-dom";
import { toast } from "sonner";

import { useEventSocket } from "@/hooks/useEventSocket";
import { publishServerEvent } from "@/services/events";
import type { ServerEvent } from "@/types/api";

import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

function notify(event: ServerEvent) {
  if (event.type === "stream.went_live") {
    toast.success(`${event.name} canlı yayında`, {
      description: event.title ?? undefined,
      action: event.stream_url
        ? { label: "Aç", onClick: () => window.open(event.stream_url!, "_blank", "noopener,noreferrer") }
        : undefined,
    });
  } else if (event.type === "stream.went_offline") {
    toast(`${event.name} yayını bitirdi`);
  } else if (event.type === "recording.started") {
    toast(`${event.name} kaydediliyor`, { description: "Canlı kayıt başladı." });
  } else if (event.type === "recording.finished") {
    if (event.status === "completed") toast.success("Kayıt tamamlandı", { description: "Kayıtlar sayfasından izleyebilirsiniz." });
    else toast.error("Kayıt başarısız", { description: "Ayrıntılar Kayıtlar sayfasında." });
  }
}

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const socketState = useEventSocket((event) => {
    notify(event);
    publishServerEvent(event);
  });

  return (
    <div className="min-h-svh">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-h-svh flex-col lg:pl-64">
        <Header onMenuClick={() => setSidebarOpen(true)} socketState={socketState} />
        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
