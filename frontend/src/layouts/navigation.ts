import {
  BrainCircuit,
  CalendarClock,
  Film,
  LayoutDashboard,
  type LucideIcon,
  Scissors,
  Settings,
  Users,
  SquarePlay,
} from "lucide-react";

export interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
  /** Roadmap phase that will implement the page; undefined = available now. */
  phase?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "Genel Bakış", icon: LayoutDashboard },
  { path: "/streamers", label: "Yayıncı Yönetimi", icon: Users },
  { path: "/schedule", label: "Yayın Takvimi", icon: CalendarClock },
  { path: "/recordings", label: "Kayıtlar", icon: Film },
  { path: "/clips", label: "AI Kesitleri", icon: Scissors, phase: "Aşama 6–7" },
  { path: "/youtube", label: "YouTube Yönetimi", icon: SquarePlay, phase: "Aşama 9–10" },
  { path: "/ai-models", label: "AI Model Ayarları", icon: BrainCircuit, phase: "Aşama 4–5" },
  { path: "/settings", label: "Sistem Ayarları", icon: Settings, phase: "Sonraki aşama" },
];
