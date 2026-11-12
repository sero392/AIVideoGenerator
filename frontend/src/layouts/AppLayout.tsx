import { useState } from "react";
import { Outlet } from "react-router-dom";

import { useEventSocket } from "@/hooks/useEventSocket";

import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const socketState = useEventSocket();

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
