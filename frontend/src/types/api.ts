// Mirrors backend/app/schemas. Keep in sync when the API changes.

export interface HealthResponse {
  status: "ok";
  application: string;
  version: string;
}

export type ComponentState = "ok" | "unavailable" | "disabled" | "error";

export interface DashboardStats {
  tracked_streamers: number;
  active_streams: number;
  total_recordings: number;
  prepared_clips: number;
}

export interface ActivityItem {
  kind: "recording" | "clip" | "youtube";
  title: string;
  status: string;
  timestamp: string;
}

export interface ComponentStatus {
  name: string;
  status: ComponentState;
  detail: string | null;
}

export interface SystemStatus {
  overall: "ok" | "degraded" | "error";
  components: ComponentStatus[];
}

export interface DashboardSummary {
  stats: DashboardStats;
  recent_activity: ActivityItem[];
  system_status: SystemStatus;
  generated_at: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export type ServerEvent =
  | { type: "connected" }
  | { type: "pong" }
  | { type: "heartbeat"; timestamp: string };
