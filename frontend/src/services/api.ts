import type {
  ApiErrorBody,
  InboxScanResponse,
  Recording,
  RecordingFilters,
  RecordingList,
  RecordingSystemInfo,
  DashboardSummary,
  HealthResponse,
  ScheduleRead,
  StreamEventItem,
  TrackedStreamer,
  TrackingOverview,
  TrackingWindowInput,
  Streamer,
  StreamerFilters,
  StreamerImportResult,
  StreamerInput,
  StreamerList,
} from "@/types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
export const API_V1 = `${API_BASE}/api/v1`;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** Field name -> message, from validation error details (`loc: ["body", field]`). */
  readonly fieldErrors: Record<string, string>;

  constructor(status: number, code: string, message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

function extractFieldErrors(details: unknown): Record<string, string> {
  if (!Array.isArray(details)) return {};
  const result: Record<string, string> = {};
  for (const item of details) {
    const loc = (item as { loc?: unknown[] })?.loc;
    const msg = (item as { msg?: string })?.msg;
    if (Array.isArray(loc) && loc[0] === "body" && typeof loc[loc.length - 1] === "string" && msg) {
      result[loc[loc.length - 1] as string] ??= msg;
    }
  }
  return result;
}

type Query = Record<string, string | number | boolean | undefined | null>;

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

/** Build an ApiError from a non-OK response body (shared by fetch and XHR uploads). */
function errorFrom(status: number, body: Partial<ApiErrorBody>): ApiError {
  return new ApiError(
    status,
    body.error?.code ?? "http_error",
    body.error?.message ?? `İstek başarısız (${status}).`,
    extractFieldErrors(body.error?.details),
  );
}

async function request<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  let response: Response;
  try {
    response = await fetch(`${API_V1}${path}`, {
      ...rest,
      headers: {
        Accept: "application/json",
        ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
        ...rest.headers,
      },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "network_error", "Backend'e ulaşılamıyor.");
  }

  if (!response.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = await response.json();
    } catch {
      /* non-JSON error */
    }
    throw errorFrom(response.status, body);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>("/health", { signal }),
  dashboardSummary: (signal?: AbortSignal) => request<DashboardSummary>("/dashboard/summary", { signal }),

  streamers: {
    list: (filters: StreamerFilters, signal?: AbortSignal) =>
      request<StreamerList>(withQuery("/streamers", filters as Query), { signal }),
    create: (input: StreamerInput) => request<Streamer>("/streamers", { method: "POST", json: input }),
    update: (id: number, input: Partial<StreamerInput>) =>
      request<Streamer>(`/streamers/${id}`, { method: "PATCH", json: input }),
    remove: (id: number) => request<void>(`/streamers/${id}`, { method: "DELETE" }),
    importFromConfig: () => request<StreamerImportResult>("/streamers/import", { method: "POST" }),
    getSchedule: (id: number) => request<ScheduleRead>(`/streamers/${id}/schedule`),
    putSchedule: (id: number, windows: TrackingWindowInput[]) =>
      request<ScheduleRead>(`/streamers/${id}/schedule`, { method: "PUT", json: { windows } }),
  },

  recordings: {
    list: (filters: RecordingFilters, signal?: AbortSignal) =>
      request<RecordingList>(withQuery("/recordings", filters as Query), { signal }),
    system: (signal?: AbortSignal) => request<RecordingSystemInfo>("/recordings/system", { signal }),
    startLive: (streamerId: number) =>
      request<Recording>("/recordings/live", { method: "POST", json: { streamer_id: streamerId } }),
    stop: (id: number) => request<Recording>(`/recordings/${id}/stop`, { method: "POST" }),
    remove: (id: number) => request<void>(`/recordings/${id}`, { method: "DELETE" }),
    scanInbox: () => request<InboxScanResponse>("/recordings/inbox/scan", { method: "POST" }),
    fileUrl: (id: number) => `${API_V1}/recordings/${id}/file`,
    upload: uploadRecording,
  },

  tracking: {
    overview: (signal?: AbortSignal) => request<TrackingOverview>("/tracking/overview", { signal }),
    events: (limit = 20, signal?: AbortSignal) =>
      request<StreamEventItem[]>(withQuery("/tracking/events", { limit }), { signal }),
    checkNow: (streamerId: number) =>
      request<TrackedStreamer>(`/tracking/streamers/${streamerId}/check`, { method: "POST" }),
  },
};

/** ws(s)://host/api/v1/ws/events — honours VITE_API_BASE_URL when set. */
export function eventsSocketUrl(): string {
  const base = API_BASE || window.location.origin;
  return `${base.replace(/^http/, "ws")}/api/v1/ws/events`;
}

/**
 * Multipart upload with progress (fetch has no upload progress events, so XHR is used).
 * Resolves with the created recording; rejects with ApiError.
 */
export function uploadRecording(
  input: { streamerId: number; file: File; title?: string },
  onProgress?: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<Recording> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("streamer_id", String(input.streamerId));
    if (input.title) form.append("title", input.title);
    form.append("file", input.file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_V1}/recordings/import`);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.onload = () => {
      let body: unknown = {};
      try {
        body = JSON.parse(xhr.responseText || "{}");
      } catch {
        /* non-JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as Recording);
      else reject(errorFrom(xhr.status, body as Partial<ApiErrorBody>));
    };
    xhr.onerror = () => reject(new ApiError(0, "network_error", "Backend'e ulaşılamıyor."));
    xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort());
    xhr.send(form);
  });
}
