import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "@/App";
import { api } from "@/services/api";
import type { Recording, RecordingSystemInfo, Streamer } from "@/types/api";
import { formatBytes, formatDuration } from "@/utils/format";

const rec = (over: Partial<Recording> = {}): Recording => ({
  id: 1,
  streamer_id: 2,
  streamer_name: "apex",
  platform: "youtube",
  source: "import",
  title: "Turnuva finali",
  source_url: "final.mp4",
  status: "completed",
  stop_reason: null,
  started_at: null,
  ended_at: "2026-11-16T12:00:00Z",
  duration_seconds: 3725,
  file_size_bytes: 1536 * 1024 * 1024,
  file_available: true,
  error_message: null,
  created_at: "2026-11-16T12:00:00Z",
  ...over,
});

const system: RecordingSystemInfo = {
  ffmpeg_available: true,
  ffmpeg_source: "bundled",
  ytdlp_version: "2026.10.26",
  js_runtime_available: true,
  free_gb: 151.6,
  min_free_gb: 5,
  max_concurrent: 2,
  active_count: 0,
  max_hours: 12,
  max_upload_gb: 20,
  inbox_path: "storage/recordings/inbox",
  allowed_extensions: [".mkv", ".mp4"],
};

const streamer = (over: Partial<Streamer>): Streamer => ({
  id: 2,
  name: "apex",
  platform: "youtube",
  channel_url: "https://youtube.com/@apex",
  is_active: true,
  recording_permission_confirmed: true,
  permission_notes: "ok",
  permission_confirmed_at: null,
  live_capture_enabled: false,
  created_at: "2026-11-16T10:00:00Z",
  updated_at: null,
  recordings_count: 0,
  clips_count: 0,
  ...over,
});

function mockApi(opts: { items?: Recording[]; active?: Recording[]; streamers?: Streamer[] }) {
  const calls: { method: string; path: string; search: string }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const url = new URL(String(input), "http://localhost");
    const method = (init.method ?? "GET").toUpperCase();
    const path = url.pathname.replace("/api/v1", "");
    calls.push({ method, path, search: url.search });
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (path === "/recordings/system") return json(system);
    if (path === "/recordings" && url.searchParams.get("status") === "recording")
      return json({ items: opts.active ?? [], total: (opts.active ?? []).length, limit: 10, offset: 0 });
    if (path === "/recordings") return json({ items: opts.items ?? [], total: (opts.items ?? []).length, limit: 25, offset: 0 });
    if (path === "/streamers") return json({ items: opts.streamers ?? [], total: 0, limit: 100, offset: 0 });
    if (method === "POST" && path.endsWith("/stop")) return json(rec({ status: "processing" }));
    if (method === "DELETE") return new Response(null, { status: 204 });
    return json({ version: "0.4.0" });
  });
  return calls;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/recordings"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("format helpers", () => {
  it("formats durations and sizes", () => {
    expect(formatDuration(3725)).toBe("1:02:05");
    expect(formatDuration(65)).toBe("1:05");
    expect(formatDuration(null)).toBe("—");
    expect(formatBytes(1536 * 1024 * 1024)).toBe("1,5 GB");
    expect(formatBytes(512)).toBe("512 B");
  });
});

describe("RecordingsPage", () => {
  it("lists recordings with tool status", async () => {
    mockApi({ items: [rec(), rec({ id: 2, source: "live_capture", status: "failed", file_available: false, error_message: "Hiç görüntü kaydedilemedi" })] });
    renderPage();
    const row = await screen.findByTestId("recording-row-1");
    expect(within(row).getByText("Turnuva finali")).toBeInTheDocument();
    expect(within(row).getByText("1:02:05")).toBeInTheDocument();
    expect(within(row).getByText("İçe aktarma")).toBeInTheDocument();
    const failed = screen.getByTestId("recording-row-2");
    expect(within(failed).getByText("Başarısız")).toBeInTheDocument();
    expect(within(failed).getByText("Hiç görüntü kaydedilemedi")).toBeInTheDocument();
    expect(within(failed).getByRole("button", { name: /izle/ })).toBeDisabled();
    expect(screen.getByText("Hazır (proje içi)")).toBeInTheDocument();
    expect(screen.getByText("yt-dlp 2026.10.26")).toBeInTheDocument();
  });

  it("shows active recordings and stops one", async () => {
    const calls = mockApi({ active: [rec({ id: 9, status: "recording", source: "live_capture", started_at: new Date(Date.now() - 65_000).toISOString() })] });
    const user = userEvent.setup();
    renderPage();
    const card = await screen.findByTestId("active-9");
    expect(within(card).getByText(/1:0\d/)).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: /Durdur/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/recordings/9/stop")).toBe(true));
  });

  it("deletes after confirmation", async () => {
    const calls = mockApi({ items: [rec()] });
    const user = userEvent.setup();
    renderPage();
    await user.click(within(await screen.findByTestId("recording-row-1")).getByRole("button", { name: /sil/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/1,5 GB/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Kalıcı olarak sil" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/recordings/1")).toBe(true));
  });

  it("uploads a file for a permitted streamer only", async () => {
    mockApi({ streamers: [streamer({}), streamer({ id: 3, name: "izinsiz", recording_permission_confirmed: false })] });
    const upload = vi.spyOn(api.recordings, "upload").mockImplementation(async (_input, onProgress) => {
      onProgress?.(1);
      return rec({ title: "yeni" });
    });
    // applyAccept: false lets the test hand over a file the browser picker would normally filter out
    const user = userEvent.setup({ applyAccept: false });
    renderPage();
    await user.click(await screen.findByRole("button", { name: /Dosya yükle/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("option", { name: /izinsiz \(izin onaylanmamış\)/ })).toBeDisabled();

    const input = dialog.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["x"], "notes.txt", { type: "text/plain" }));
    await user.click(within(dialog).getByRole("button", { name: "Yükle" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Desteklenmeyen dosya türü");

    await user.upload(input, new File(["video"], "final.mp4", { type: "video/mp4" }));
    await user.type(within(dialog).getByLabelText(/Başlık/), "Final");
    await user.click(within(dialog).getByRole("button", { name: "Yükle" }));
    await waitFor(() => expect(upload).toHaveBeenCalled());
    expect(upload.mock.calls[0][0]).toMatchObject({ streamerId: 2, title: "Final" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

describe("Streamer form live capture toggle", () => {
  it("is disabled until permission is confirmed and shows the terms warning", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(JSON.stringify({ items: [], total: 0, limit: 20, offset: 0 })));
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/streamers"]}>
        <App />
      </MemoryRouter>,
    );
    await user.click((await screen.findAllByRole("button", { name: /Yayıncı Ekle/ }))[0]);
    const dialog = await screen.findByRole("dialog");
    const toggle = within(dialog).getByRole("switch", { name: /Canlı yayını otomatik kaydet/ });
    expect(toggle).toBeDisabled();
    await user.click(within(dialog).getByLabelText(/Kayıt ve yeniden yayın izni alındı/));
    expect(toggle).toBeEnabled();
    await user.click(toggle);
    expect(within(dialog).getByRole("note")).toHaveTextContent("kullanım koşulları");
    await user.click(within(dialog).getByLabelText(/Kayıt ve yeniden yayın izni alındı/));
    expect(toggle).toBeDisabled();
    expect(toggle).toHaveAttribute("aria-checked", "false"); // revoking permission switches capture off
  });
});
