import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "@/App";
import { validateStreamer } from "@/components/streamers/StreamerFormDialog";
import type { Streamer } from "@/types/api";

const base: Streamer = {
  id: 1,
  name: "Alpha",
  platform: "twitch",
  channel_url: "https://twitch.tv/alpha",
  is_active: true,
  recording_permission_confirmed: true,
  permission_notes: "Yazılı izin",
  permission_confirmed_at: "2026-11-10T10:00:00Z",
  live_capture_enabled: false,
  created_at: "2026-11-10T10:00:00Z",
  updated_at: null,
  recordings_count: 0,
  clips_count: 0,
};

type Handler = (url: URL, init: RequestInit) => { status: number; body?: unknown };

/** Route fetch calls by "METHOD /path"; records every call for assertions. */
function mockApi(routes: Record<string, Handler>) {
  const calls: { method: string; path: string; body: unknown; search: string }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const url = new URL(String(input), "http://localhost");
    const method = (init.method ?? "GET").toUpperCase();
    const path = url.pathname.replace("/api/v1", "");
    calls.push({ method, path, search: url.search, body: init.body ? JSON.parse(String(init.body)) : undefined });
    const handler = routes[`${method} ${path}`] ?? routes[`${method} ${path.replace(/\/\d+$/, "/:id")}`];
    const { status, body } = handler ? handler(url, init) : { status: 404, body: {} };
    return new Response(status === 204 ? null : JSON.stringify(body ?? {}), { status });
  });
  return calls;
}

const list = (items: Streamer[]) => () => ({ status: 200, body: { items, total: items.length, limit: 20, offset: 0 } });
const health = () => ({ status: 200, body: { status: "ok", application: "x", version: "0.1.0" } });

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/streamers"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("validateStreamer", () => {
  it("requires notes when permission is confirmed", () => {
    const errors = validateStreamer({
      name: " ",
      platform: "twitch",
      channel_url: "http://twitch.tv/x",
      is_active: true,
      recording_permission_confirmed: true,
      permission_notes: "",
      live_capture_enabled: false,
    });
    expect(Object.keys(errors).sort()).toEqual(["channel_url", "name", "permission_notes"]);
  });
});

describe("StreamersPage", () => {
  it("shows the empty state when there are no streamers", async () => {
    mockApi({ "GET /streamers": list([]), "GET /health": health });
    renderPage();
    expect(await screen.findByText("Henüz yayıncı eklenmedi")).toBeInTheDocument();
  });

  it("lists streamers with platform and permission badges", async () => {
    mockApi({
      "GET /streamers": list([base, { ...base, id: 2, name: "Beta", platform: "kick", recording_permission_confirmed: false }]),
      "GET /health": health,
    });
    renderPage();
    const row = await screen.findByTestId("streamer-row-1");
    expect(within(row).getByText("Alpha")).toBeInTheDocument();
    expect(within(row).getByText("İzin onaylı")).toBeInTheDocument();
    expect(within(screen.getByTestId("streamer-row-2")).getByText("İzin yok")).toBeInTheDocument();
  });

  it("sends filters to the API", async () => {
    const calls = mockApi({ "GET /streamers": list([base]), "GET /health": health });
    renderPage();
    await screen.findByTestId("streamer-row-1");
    await userEvent.selectOptions(screen.getByLabelText("Platform filtresi"), "kick");
    await waitFor(() => expect(calls.some((c) => c.path === "/streamers" && c.search.includes("platform=kick"))).toBe(true));
  });

  it("creates a streamer and shows server-side field errors", async () => {
    let attempt = 0;
    const calls = mockApi({
      "GET /streamers": list([]),
      "GET /health": health,
      "POST /streamers": () =>
        ++attempt === 1
          ? {
              status: 422,
              body: {
                error: {
                  code: "validation_error",
                  message: "x",
                  details: [{ loc: ["body", "channel_url"], msg: "Bu platform için adres twitch.tv olmalıdır." }],
                },
              },
            }
          : { status: 201, body: { ...base, name: "New" } },
    });
    const user = userEvent.setup();
    renderPage();
    await user.click((await screen.findAllByRole("button", { name: /Yayıncı Ekle/ }))[0]);

    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Yayıncı adı"), "New");
    await user.type(within(dialog).getByLabelText("Kanal adresi"), "https://kick.com/new");
    await user.click(within(dialog).getByRole("button", { name: "Yayıncı Ekle" }));
    expect(await within(dialog).findByText("Bu platform için adres twitch.tv olmalıdır.")).toBeInTheDocument();

    const url = within(dialog).getByLabelText("Kanal adresi");
    await user.clear(url);
    await user.type(url, "https://twitch.tv/new");
    await user.click(within(dialog).getByRole("button", { name: "Yayıncı Ekle" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    const posts = calls.filter((c) => c.method === "POST");
    expect(posts.at(-1)?.body).toMatchObject({ name: "New", channel_url: "https://twitch.tv/new", permission_notes: null });
  });

  it("blocks submit until permission notes are filled", async () => {
    const calls = mockApi({ "GET /streamers": list([]), "GET /health": health });
    const user = userEvent.setup();
    renderPage();
    await user.click((await screen.findAllByRole("button", { name: /Yayıncı Ekle/ }))[0]);
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Yayıncı adı"), "X");
    await user.type(within(dialog).getByLabelText("Kanal adresi"), "https://twitch.tv/x");
    await user.click(within(dialog).getByLabelText(/Kayıt ve yeniden yayın izni alındı/));
    await user.click(within(dialog).getByRole("button", { name: "Yayıncı Ekle" }));
    expect(within(dialog).getByText(/iznin kimden ve nasıl alındığını/)).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("offers deactivation instead of delete when recordings exist", async () => {
    const calls = mockApi({
      "GET /streamers": list([{ ...base, recordings_count: 3 }]),
      "GET /health": health,
      "PATCH /streamers/:id": () => ({ status: 200, body: { ...base, is_active: false } }),
    });
    const user = userEvent.setup();
    renderPage();
    const row = await screen.findByTestId("streamer-row-1");
    await user.click(within(row).getByRole("button", { name: "Alpha sil" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByRole("button", { name: "Kalıcı olarak sil" })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Pasif yap" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ is_active: false });
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("deletes a streamer without recordings after confirmation", async () => {
    const calls = mockApi({
      "GET /streamers": list([base]),
      "GET /health": health,
      "DELETE /streamers/:id": () => ({ status: 204 }),
    });
    const user = userEvent.setup();
    renderPage();
    const row = await screen.findByTestId("streamer-row-1");
    await user.click(within(row).getByRole("button", { name: "Alpha sil" }));
    await user.click(await screen.findByRole("button", { name: "Kalıcı olarak sil" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/streamers/1")).toBe(true));
  });

  it("shows the import summary", async () => {
    mockApi({
      "GET /streamers": list([]),
      "GET /health": health,
      "POST /streamers/import": () => ({
        status: 200,
        body: { created: [base], skipped: [{ channel_url: "https://kick.com/b", reason: "Zaten kayıtlı" }], errors: [] },
      }),
    });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: /içe aktar/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Eklendi (1)")).toBeInTheDocument();
    expect(within(dialog).getByText("Atlandı (1)")).toBeInTheDocument();
  });
});
