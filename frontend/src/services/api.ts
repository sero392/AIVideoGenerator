import type { ApiErrorBody, DashboardSummary, HealthResponse } from "@/types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
export const API_V1 = `${API_BASE}/api/v1`;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_V1}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "network_error", "Backend'e ulaşılamıyor.");
  }

  if (!response.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = await response.json();
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(
      response.status,
      body.error?.code ?? "http_error",
      body.error?.message ?? `İstek başarısız (${response.status}).`,
    );
  }
  return (await response.json()) as T;
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>("/health", { signal }),
  dashboardSummary: (signal?: AbortSignal) => request<DashboardSummary>("/dashboard/summary", { signal }),
};

/** ws(s)://host/api/v1/ws/events — honours VITE_API_BASE_URL when set. */
export function eventsSocketUrl(): string {
  const base = API_BASE || window.location.origin;
  return `${base.replace(/^http/, "ws")}/api/v1/ws/events`;
}
