import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "@/App";
import type { DashboardSummary } from "@/types/api";

const emptySummary: DashboardSummary = {
  stats: { tracked_streamers: 0, active_streams: 0, total_recordings: 0, prepared_clips: 0 },
  recent_activity: [],
  system_status: {
    overall: "degraded",
    components: [
      { name: "database", status: "ok", detail: "SQLite" },
      { name: "ollama", status: "unavailable", detail: "Ollama not reachable" },
    ],
  },
  generated_at: "2026-11-12T10:00:00Z",
};

function mockFetch(routes: Record<string, unknown>, fail = false) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    if (fail) throw new TypeError("Failed to fetch");
    const url = String(input);
    const key = Object.keys(routes).find((path) => url.endsWith(path));
    return new Response(JSON.stringify(key ? routes[key] : {}), { status: key ? 200 : 404 });
  });
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("App shell", () => {
  it("renders all sidebar sections", () => {
    mockFetch({});
    renderAt("/");
    for (const label of [
      "Yayıncı Yönetimi",
      "Yayın Takvimi",
      "Kayıtlar",
      "AI Kesitleri",
      "YouTube Yönetimi",
      "AI Model Ayarları",
      "Sistem Ayarları",
    ]) {
      expect(screen.getByRole("link", { name: new RegExp(label) })).toBeInTheDocument();
    }
  });

  it("shows a 'not yet implemented' page for future modules", () => {
    mockFetch({});
    renderAt("/recordings");
    expect(screen.getByText(/Bu modül henüz geliştirilmedi/)).toBeInTheDocument();
  });
});

describe("Overview page", () => {
  it("shows real zeros and empty states from an empty database", async () => {
    mockFetch({
      "/api/v1/dashboard/summary": emptySummary,
      "/api/v1/health": { status: "ok", application: "Streamer AI Engine", version: "0.1.0" },
    });
    renderAt("/");

    expect(await screen.findByTestId("stat-Takip Edilen Yayıncı")).toHaveTextContent("0");
    expect(screen.getByTestId("stat-Hazırlanan Kesit")).toHaveTextContent("0");
    expect(screen.getByText("Henüz işlem yok")).toBeInTheDocument();
    expect(screen.getByText("Ollama (Qwen)")).toBeInTheDocument();
    expect(await screen.findByText("API v0.1.0")).toBeInTheDocument();
  });

  it("shows an error and no fake numbers when the backend is down", async () => {
    mockFetch({}, true);
    renderAt("/");

    expect(await screen.findByRole("alert")).toHaveTextContent("Backend verisi alınamadı");
    expect(screen.getByTestId("stat-Toplam Kayıt")).toHaveTextContent("—");
  });
});
