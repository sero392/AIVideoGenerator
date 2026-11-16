import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "@/App";
import { validateWindows } from "@/components/schedule/ScheduleEditorDialog";
import type { TrackedStreamer, TrackingOverview } from "@/types/api";
import { formatWindow, weekSegments } from "@/utils/schedule";

import { FakeWebSocket } from "./setup";

const streamer = (over: Partial<TrackedStreamer> = {}): TrackedStreamer => ({
  id: 1,
  name: "Easter",
  platform: "youtube",
  channel_url: "https://youtube.com/@easter",
  is_active: true,
  recording_permission_confirmed: true,
  live_capture_enabled: false,
  active_recording_id: null,
  windows: [{ id: 10, day_of_week: 0, start_time: "20:00", end_time: "23:00" }],
  status: {
    state: "offline",
    title: null,
    viewer_count: null,
    live_started_at: null,
    stream_url: null,
    error_message: null,
    checked_at: "2026-11-16T12:00:00Z",
    state_changed_at: null,
  },
  in_schedule: false,
  next_change_at: "2026-11-16T17:00:00Z",
  ...over,
});

const overview = (streamers: TrackedStreamer[], configured = false): TrackingOverview => ({
  timezone: "Europe/Istanbul",
  tracking_enabled: true,
  tick_seconds: 60,
  next_cycle_at: null,
  live_count: streamers.filter((s) => s.status.state === "live").length,
  platforms: [
    { platform: "twitch", configured: false, required_settings: ["TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"], poll_interval_seconds: 120 },
    { platform: "youtube", configured, required_settings: ["YOUTUBE_API_KEY"], poll_interval_seconds: 300 },
  ],
  streamers,
});

type Route = (body: unknown) => { status: number; body?: unknown };

function mockApi(routes: Record<string, Route>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const url = new URL(String(input), "http://localhost");
    const method = (init.method ?? "GET").toUpperCase();
    const path = url.pathname.replace("/api/v1", "");
    const body = init.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    const route = routes[`${method} ${path}`];
    const res = route ? route(body) : { status: path === "/health" ? 200 : 404, body: { version: "0.2.0" } };
    return new Response(JSON.stringify(res.body ?? {}), { status: res.status });
  });
  return calls;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/schedule"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("schedule utils", () => {
  it("splits windows that cross midnight", () => {
    const days = weekSegments([
      { day_of_week: 6, start_time: "22:00", end_time: "02:00" },
      { day_of_week: 2, start_time: "00:00", end_time: "00:00" },
    ]);
    expect(days[6]).toEqual([[1320, 1440]]);
    expect(days[0]).toEqual([[0, 120]]); // Sunday night continues into Monday
    expect(days[2]).toEqual([[0, 1440]]);
    expect(days[3]).toEqual([]);
    expect(formatWindow({ day_of_week: 4, start_time: "22:00", end_time: "02:00" })).toBe("Cum 22:00–02:00 (+1)");
    expect(formatWindow({ day_of_week: 0, start_time: "08:00", end_time: "08:00" })).toBe("Pzt 24 saat");
  });

  it("validates windows like the backend", () => {
    const w = { day_of_week: 1, start_time: "20:00", end_time: "21:00" };
    expect(validateWindows([w])).toBeNull();
    expect(validateWindows([w, w])).toMatch(/birden fazla/);
    expect(validateWindows([{ ...w, start_time: "" }])).toMatch(/SS:DD/);
  });
});

describe("SchedulePage", () => {
  it("shows platform setup hints and the streamer card", async () => {
    mockApi({ "GET /tracking/overview": () => ({ status: 200, body: overview([streamer()]) }), "GET /tracking/events": () => ({ status: 200, body: [] }) });
    renderPage();
    const card = await screen.findByTestId("tracked-1");
    expect(within(card).getByText("Çevrimdışı")).toBeInTheDocument();
    expect(within(card).getByText(/Sonraki takip:/)).toBeInTheDocument();
    expect(screen.getByText("YOUTUBE_API_KEY")).toBeInTheDocument();
    expect(screen.getByText("Henüz yayın hareketi kaydedilmedi.")).toBeInTheDocument();
  });

  it("renders a live stream with a permission warning", async () => {
    const live = streamer({
      recording_permission_confirmed: false,
      in_schedule: true,
      status: { ...streamer().status, state: "live", title: "Turnuva", viewer_count: 1234, stream_url: "https://www.youtube.com/watch?v=x" },
    });
    mockApi({ "GET /tracking/overview": () => ({ status: 200, body: overview([live], true) }), "GET /tracking/events": () => ({ status: 200, body: [] }) });
    renderPage();
    const card = await screen.findByTestId("tracked-1");
    expect(within(card).getByText("Canlı")).toBeInTheDocument();
    expect(within(card).getByText("Turnuva")).toBeInTheDocument();
    expect(within(card).getByText(/1\.234 izleyici/)).toBeInTheDocument();
    expect(within(card).getByText(/kaydedilmeyecek/)).toBeInTheDocument();
    expect(screen.getByText("Bağlı")).toBeInTheDocument();
  });

  it("edits and saves the weekly schedule", async () => {
    const calls = mockApi({
      "GET /tracking/overview": () => ({ status: 200, body: overview([streamer({ windows: [] })]) }),
      "GET /tracking/events": () => ({ status: 200, body: [] }),
      "PUT /streamers/1/schedule": (body) => ({ status: 200, body: { streamer_id: 1, timezone: "Europe/Istanbul", windows: (body as { windows: unknown[] }).windows } }),
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: /Takvimi düzenle/ }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Hafta sonu (12:00–02:00)" }));
    await user.click(within(dialog).getByRole("button", { name: "Takvimi kaydet" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
      windows: [
        { day_of_week: 5, start_time: "12:00", end_time: "02:00" },
        { day_of_week: 6, start_time: "12:00", end_time: "02:00" },
      ],
    });
  });

  it("runs a manual check", async () => {
    const calls = mockApi({
      "GET /tracking/overview": () => ({ status: 200, body: overview([streamer()]) }),
      "GET /tracking/events": () => ({ status: 200, body: [] }),
      "POST /tracking/streamers/1/check": () => ({ status: 200, body: streamer({ status: { ...streamer().status, state: "not_configured" } }) }),
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: /Şimdi kontrol et/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/tracking/streamers/1/check")).toBe(true));
    expect(await screen.findByText("Easter: API ayarı yok")).toBeInTheDocument();
  });

  it("refreshes and notifies when the backend pushes a went_live event", async () => {
    const calls = mockApi({
      "GET /tracking/overview": () => ({ status: 200, body: overview([streamer()]) }),
      "GET /tracking/events": () => ({ status: 200, body: [] }),
    });
    renderPage();
    await screen.findByTestId("tracked-1");
    const before = calls.filter((c) => c.path === "/tracking/overview").length;
    act(() => {
      FakeWebSocket.instances.at(-1)!.emit({
        type: "stream.went_live",
        streamer_id: 1,
        name: "Easter",
        platform: "youtube",
        title: "Yeni yayın",
        stream_url: null,
      });
    });
    expect(await screen.findByText("Easter canlı yayında")).toBeInTheDocument();
    await waitFor(() => expect(calls.filter((c) => c.path === "/tracking/overview").length).toBeGreaterThan(before));
  });
});
