import { AlertTriangle, ExternalLink, FileJson, Loader2, Pencil, Plus, Search, Trash2, Users } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { PermissionBadge, PlatformBadge } from "@/components/streamers/StreamerBadges";
import { DeleteStreamerDialog } from "@/components/streamers/DeleteStreamerDialog";
import { ImportResultDialog } from "@/components/streamers/ImportResultDialog";
import { StreamerFormDialog } from "@/components/streamers/StreamerFormDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApiQuery } from "@/hooks/useApiQuery";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { ApiError, api } from "@/services/api";
import type { StreamPlatform, Streamer, StreamerFilters, StreamerImportResult, StreamerInput } from "@/types/api";
import { formatDateTime } from "@/utils/format";
import { PLATFORM_OPTIONS, shortUrl } from "@/utils/streamers";

const PAGE_SIZE = 20;

type TriState = "all" | "yes" | "no";
const triToBool = (v: TriState) => (v === "all" ? undefined : v === "yes");

function errorMessage(err: unknown) {
  return err instanceof ApiError ? err.message : "Beklenmeyen bir hata oluştu.";
}

export function StreamersPage() {
  const [search, setSearch] = useState("");
  const [platform, setPlatform] = useState<StreamPlatform | "all">("all");
  const [active, setActive] = useState<TriState>("all");
  const [permission, setPermission] = useState<TriState>("all");
  const [page, setPage] = useState(0);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Streamer | null>(null);
  const [deleting, setDeleting] = useState<Streamer | null>(null);
  const [importResult, setImportResult] = useState<StreamerImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const debouncedSearch = useDebouncedValue(search.trim());
  const filters: StreamerFilters = {
    search: debouncedSearch || undefined,
    platform: platform === "all" ? undefined : platform,
    is_active: triToBool(active),
    permission_confirmed: triToBool(permission),
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  };
  const { data, error, loading, refetch } = useApiQuery((signal) => api.streamers.list(filters, signal), {
    deps: [filters],
  });

  const hasFilters = Boolean(debouncedSearch) || platform !== "all" || active !== "all" || permission !== "all";
  const resetPage = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setPage(0);
  };

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };
  const openEdit = (s: Streamer) => {
    setEditing(s);
    setFormOpen(true);
  };

  const handleSubmit = useCallback(
    async (input: StreamerInput) => {
      if (editing) {
        const updated = await api.streamers.update(editing.id, input);
        toast.success(`${updated.name} güncellendi.`);
      } else {
        const created = await api.streamers.create(input);
        toast.success(`${created.name} eklendi.`);
      }
      refetch();
    },
    [editing, refetch],
  );

  const toggleActive = async (s: Streamer, isActive: boolean) => {
    setTogglingId(s.id);
    try {
      await api.streamers.update(s.id, { is_active: isActive });
      toast.success(`${s.name} ${isActive ? "aktif" : "pasif"} yapıldı.`);
      refetch();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (s: Streamer) => {
    await api.streamers.remove(s.id);
    toast.success(`${s.name} silindi.`);
    if (data && data.items.length === 1 && page > 0) setPage(page - 1);
    else refetch();
  };

  const handleDeactivate = async (s: Streamer) => {
    await api.streamers.update(s.id, { is_active: false });
    toast.success(`${s.name} pasif yapıldı.`);
    refetch();
  };

  const handleImport = async () => {
    setImporting(true);
    try {
      const result = await api.streamers.importFromConfig();
      setImportResult(result);
      if (result.created.length) refetch();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setImporting(false);
    }
  };

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const initialLoading = loading && !data && !error;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Yayıncı Yönetimi</h2>
          <p className="text-muted-foreground text-sm">
            {data ? `${total} yayıncı${hasFilters ? " (filtreli)" : ""}` : "Takip edilecek yayıncıları yönetin"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleImport} disabled={importing} title="config/streamers.json dosyasından ekle">
            {importing ? <Loader2 className="animate-spin" /> : <FileJson />}
            <span className="hidden sm:inline">JSON'dan içe aktar</span>
            <span className="sm:hidden">İçe aktar</span>
          </Button>
          <Button onClick={openCreate}>
            <Plus />
            Yayıncı Ekle
          </Button>
        </div>
      </div>

      <Card className="gap-0 py-0">
        <div className="grid grid-cols-1 gap-3 border-b p-4 sm:grid-cols-2 lg:grid-cols-[1fr_10rem_10rem_11rem]">
          <div className="relative">
            <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
            <Input
              aria-label="Yayıncı ara"
              placeholder="Ad veya kanal adresi ara…"
              className="pl-9"
              value={search}
              maxLength={100}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
            />
          </div>
          <NativeSelect
            aria-label="Platform filtresi"
            value={platform}
            onChange={(e) => resetPage(setPlatform)(e.target.value as StreamPlatform | "all")}
          >
            <option value="all">Tüm platformlar</option>
            {PLATFORM_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </NativeSelect>
          <NativeSelect aria-label="Durum filtresi" value={active} onChange={(e) => resetPage(setActive)(e.target.value as TriState)}>
            <option value="all">Tüm durumlar</option>
            <option value="yes">Aktif</option>
            <option value="no">Pasif</option>
          </NativeSelect>
          <NativeSelect
            aria-label="İzin filtresi"
            value={permission}
            onChange={(e) => resetPage(setPermission)(e.target.value as TriState)}
          >
            <option value="all">Tüm izin durumları</option>
            <option value="yes">İzin onaylı</option>
            <option value="no">İzin yok</option>
          </NativeSelect>
        </div>

        {error ? (
          <div className="flex items-center gap-3 p-6" role="alert">
            <AlertTriangle className="text-destructive size-5 shrink-0" />
            <div className="text-sm">
              <p className="font-medium">Yayıncılar yüklenemedi</p>
              <p className="text-muted-foreground">{error.message}</p>
            </div>
            <Button variant="outline" size="sm" className="ml-auto" onClick={refetch}>
              Tekrar dene
            </Button>
          </div>
        ) : initialLoading ? (
          <div className="space-y-3 p-4">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState filtered={hasFilters} onCreate={openCreate} />
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden xl:block">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="pl-4">Yayıncı</TableHead>
                    <TableHead>Platform</TableHead>
                    <TableHead>Kayıt izni</TableHead>
                    <TableHead className="text-right">Kayıt / Kesit</TableHead>
                    <TableHead>Eklenme</TableHead>
                    <TableHead>Takip</TableHead>
                    <TableHead className="pr-4 text-right">
                      <span className="sr-only">İşlemler</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((s) => (
                    <TableRow key={s.id} data-testid={`streamer-row-${s.id}`} className={s.is_active ? "" : "opacity-60"}>
                      <TableCell className="max-w-72 pl-4">
                        <p className="truncate font-medium">{s.name}</p>
                        <ChannelLink url={s.channel_url} />
                      </TableCell>
                      <TableCell>
                        <PlatformBadge platform={s.platform} />
                      </TableCell>
                      <TableCell>
                        <PermissionBadge streamer={s} />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {s.recordings_count} / {s.clips_count}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{formatDateTime(s.created_at)}</TableCell>
                      <TableCell>
                        <Switch
                          aria-label={`${s.name} takibini ${s.is_active ? "durdur" : "başlat"}`}
                          checked={s.is_active}
                          disabled={togglingId === s.id}
                          onCheckedChange={(c) => toggleActive(s, c)}
                        />
                      </TableCell>
                      <TableCell className="pr-4 text-right">
                        <RowActions streamer={s} onEdit={openEdit} onDelete={setDeleting} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Mobile cards */}
            <ul className="divide-y xl:hidden">
              {items.map((s) => (
                <li key={s.id} className={`space-y-3 p-4 ${s.is_active ? "" : "opacity-60"}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{s.name}</p>
                      <ChannelLink url={s.channel_url} />
                    </div>
                    <Switch
                      aria-label={`${s.name} takibini ${s.is_active ? "durdur" : "başlat"}`}
                      checked={s.is_active}
                      disabled={togglingId === s.id}
                      onCheckedChange={(c) => toggleActive(s, c)}
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <PlatformBadge platform={s.platform} />
                    <PermissionBadge streamer={s} />
                    <span className="text-muted-foreground text-xs">
                      {s.recordings_count} kayıt · {s.clips_count} kesit
                    </span>
                    <div className="ml-auto">
                      <RowActions streamer={s} onEdit={openEdit} onDelete={setDeleting} />
                    </div>
                  </div>
                </li>
              ))}
            </ul>

            {pageCount > 1 && (
              <div className="flex items-center justify-between gap-3 border-t px-4 py-3 text-sm">
                <span className="text-muted-foreground">
                  Sayfa {page + 1} / {pageCount}
                </span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page === 0 || loading} onClick={() => setPage(page - 1)}>
                    Önceki
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page + 1 >= pageCount || loading}
                    onClick={() => setPage(page + 1)}
                  >
                    Sonraki
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      <StreamerFormDialog open={formOpen} onOpenChange={setFormOpen} streamer={editing} onSubmit={handleSubmit} />
      <DeleteStreamerDialog
        streamer={deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        onConfirm={handleDelete}
        onDeactivate={handleDeactivate}
      />
      <ImportResultDialog result={importResult} onOpenChange={(o) => !o && setImportResult(null)} />
    </div>
  );
}

function ChannelLink({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-muted-foreground hover:text-foreground inline-flex max-w-full items-center gap-1 text-xs"
    >
      <span className="truncate">{shortUrl(url)}</span>
      <ExternalLink className="size-3 shrink-0" />
    </a>
  );
}

function RowActions({
  streamer,
  onEdit,
  onDelete,
}: {
  streamer: Streamer;
  onEdit: (s: Streamer) => void;
  onDelete: (s: Streamer) => void;
}) {
  return (
    <div className="inline-flex gap-1">
      <Button variant="ghost" size="icon" aria-label={`${streamer.name} düzenle`} onClick={() => onEdit(streamer)}>
        <Pencil />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={`${streamer.name} sil`}
        className="hover:text-destructive"
        onClick={() => onDelete(streamer)}
      >
        <Trash2 />
      </Button>
    </div>
  );
}

function EmptyState({ filtered, onCreate }: { filtered: boolean; onCreate: () => void }) {
  return (
    <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
      <div className="bg-muted text-muted-foreground flex size-12 items-center justify-center rounded-full">
        <Users className="size-6" />
      </div>
      {filtered ? (
        <>
          <p className="font-medium">Filtreyle eşleşen yayıncı yok</p>
          <p className="text-muted-foreground text-sm">Arama veya filtreleri değiştirmeyi deneyin.</p>
        </>
      ) : (
        <>
          <p className="font-medium">Henüz yayıncı eklenmedi</p>
          <p className="text-muted-foreground max-w-sm text-sm">
            İçeriğini kaydetme izni aldığınız ilk yayıncıyı ekleyin ya da listeyi config/streamers.json dosyasından içe
            aktarın.
          </p>
          <Button className="mt-2" onClick={onCreate}>
            <Plus />
            Yayıncı Ekle
          </Button>
        </>
      )}
    </CardContent>
  );
}
