import { Clapperboard, X } from "lucide-react";
import { NavLink } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { NAV_ITEMS } from "./navigation";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={cn(
          "fixed inset-0 z-30 bg-black/60 backdrop-blur-sm transition-opacity lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={cn(
          "bg-sidebar text-sidebar-foreground border-sidebar-border fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r transition-transform lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-label="Ana menü"
      >
        <div className="flex h-16 items-center gap-3 px-5">
          <div className="bg-primary/15 text-primary flex size-9 items-center justify-center rounded-lg ring-1 ring-primary/30">
            <Clapperboard className="size-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold tracking-tight">Streamer AI Engine</p>
            <p className="text-muted-foreground text-xs">Yönetim Paneli</p>
          </div>
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={onClose} aria-label="Menüyü kapat">
            <X />
          </Button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map(({ path, label, icon: Icon, phase }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/"}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon className={cn("size-4 shrink-0", isActive && "text-primary")} />
                  <span className="flex-1 truncate">{label}</span>
                  {phase && <span className="text-muted-foreground/60 text-[10px] font-normal">yakında</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-sidebar-border text-muted-foreground border-t px-5 py-4 text-xs">
          Yerel AI · Ollama + Qwen · faster-whisper
        </div>
      </aside>
    </>
  );
}
