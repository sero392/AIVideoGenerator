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
  kind: "recording" | "clip" | "youtube" | "stream";
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

export interface StreamTransitionEvent {
  type: "stream.went_live" | "stream.went_offline";
  streamer_id: number;
  name: string;
  platform: StreamPlatform;
  title: string | null;
  stream_url: string | null;
}

export type ServerEvent =
  | { type: "connected" }
  | { type: "pong" }
  | { type: "heartbeat"; timestamp: string }
  | { type: "tracking.updated"; streamer_ids: number[] }
  | { type: "recording.started"; recording_id: number; streamer_id: number; name: string }
  | { type: "recording.processing"; recording_id: number }
  | { type: "recording.finished"; recording_id: number; streamer_id: number; status: RecordingStatus }
  | StreamTransitionEvent;

// --- Streamers ---------------------------------------------------------------
export type StreamPlatform = "twitch" | "youtube" | "kick" | "other";

export interface Streamer {
  id: number;
  name: string;
  platform: StreamPlatform;
  channel_url: string;
  is_active: boolean;
  recording_permission_confirmed: boolean;
  permission_notes: string | null;
  permission_confirmed_at: string | null;
  live_capture_enabled: boolean;
  created_at: string;
  updated_at: string | null;
  recordings_count: number;
  clips_count: number;
}

export interface StreamerList {
  items: Streamer[];
  total: number;
  limit: number;
  offset: number;
}

export interface StreamerInput {
  name: string;
  platform: StreamPlatform;
  channel_url: string;
  is_active: boolean;
  recording_permission_confirmed: boolean;
  permission_notes: string | null;
  live_capture_enabled: boolean;
}

export interface StreamerFilters {
  search?: string;
  platform?: StreamPlatform;
  is_active?: boolean;
  permission_confirmed?: boolean;
  limit?: number;
  offset?: number;
}

export interface StreamerImportResult {
  created: Streamer[];
  skipped: { channel_url: string; reason: string }[];
  errors: { index: number; message: string }[];
}

// --- Live tracking -----------------------------------------------------------
export type TrackingState =
  | "pending"
  | "live"
  | "offline"
  | "outside_schedule"
  | "inactive"
  | "not_configured"
  | "unsupported"
  | "error";

/** day_of_week: 0 = Monday ... 6 = Sunday. Times are "HH:MM" in the backend timezone. */
export interface TrackingWindowInput {
  day_of_week: number;
  start_time: string;
  end_time: string;
}

export interface TrackingWindow extends TrackingWindowInput {
  id: number;
}

export interface StreamStatus {
  state: TrackingState;
  title: string | null;
  viewer_count: number | null;
  live_started_at: string | null;
  stream_url: string | null;
  error_message: string | null;
  checked_at: string | null;
  state_changed_at: string | null;
}

export interface TrackedStreamer {
  id: number;
  name: string;
  platform: StreamPlatform;
  channel_url: string;
  is_active: boolean;
  recording_permission_confirmed: boolean;
  live_capture_enabled: boolean;
  active_recording_id: number | null;
  windows: TrackingWindow[];
  status: StreamStatus;
  in_schedule: boolean;
  next_change_at: string | null;
}

export interface PlatformInfo {
  platform: StreamPlatform;
  configured: boolean;
  required_settings: string[];
  poll_interval_seconds: number;
}

export interface TrackingOverview {
  timezone: string;
  tracking_enabled: boolean;
  tick_seconds: number;
  next_cycle_at: string | null;
  live_count: number;
  platforms: PlatformInfo[];
  streamers: TrackedStreamer[];
}

export interface ScheduleRead {
  streamer_id: number;
  timezone: string;
  windows: TrackingWindow[];
}

export interface StreamEventItem {
  id: number;
  streamer_id: number;
  streamer_name: string;
  platform: StreamPlatform;
  event_type: "went_live" | "went_offline";
  title: string | null;
  occurred_at: string;
}

// --- Recordings --------------------------------------------------------------
export type RecordingStatus = "scheduled" | "recording" | "processing" | "completed" | "failed" | "cancelled";
export type RecordingSource = "live_capture" | "import";

export interface Recording {
  id: number;
  streamer_id: number;
  streamer_name: string;
  platform: StreamPlatform;
  source: RecordingSource;
  title: string | null;
  source_url: string | null;
  status: RecordingStatus;
  stop_reason: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  file_size_bytes: number | null;
  file_available: boolean;
  error_message: string | null;
  created_at: string;
}

export interface RecordingList {
  items: Recording[];
  total: number;
  limit: number;
  offset: number;
}

export interface RecordingFilters {
  streamer_id?: number;
  status?: RecordingStatus;
  source?: RecordingSource;
  limit?: number;
  offset?: number;
}

export interface RecordingSystemInfo {
  ffmpeg_available: boolean;
  ffmpeg_source: "system" | "bundled" | null;
  ytdlp_version: string | null;
  js_runtime_available: boolean;
  free_gb: number;
  min_free_gb: number;
  max_concurrent: number;
  active_count: number;
  max_hours: number;
  max_upload_gb: number;
  inbox_path: string;
  allowed_extensions: string[];
}

export interface InboxScanResponse {
  imported: Recording[];
  errors: { file: string; message: string }[];
  inbox_path: string;
}
