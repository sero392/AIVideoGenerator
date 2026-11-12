import { AlertTriangle, Film, Radio, RefreshCw, Scissors, Users } from "lucide-react";

import { RecentActivityCard } from "@/components/dashboard/RecentActivityCard";
import { StatCard } from "@/components/dashboard/StatCard";
import { SystemStatusCard } from "@/components/dashboard/SystemStatusCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useApiQuery } from "@/hooks/useApiQuery";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";
import { formatDateTime } from "@/utils/format";

const REFRESH_MS = 15_000;

export function OverviewPage() {
  const { data, error, loading, refetch } = useApiQuery(api.dashboardSummary, REFRESH_MS);
  const stats = data?.stats;
  // Without data we show "—" rather than fake zeros; zeros only come from a real, empty DB.
  const initialLoading = loading && !data && !error;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Genel Bakış</h2>
          <p className="text-muted-foreground text-sm">
            {data ? `Son güncelleme: ${formatDateTime(data.generated_at)}` : "Sistem verileri yükleniyor"}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={refetch} disabled={loading}>
          <RefreshCw className={cn(loading && "animate-spin")} />
          Yenile
        </Button>
      </div>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5 py-4" role="alert">
          <CardContent className="flex items-center gap-3 px-4">
            <AlertTriangle className="text-destructive size-5 shrink-0" />
            <div className="text-sm">
              <p className="font-medium">Backend verisi alınamadı</p>
              <p className="text-muted-foreground">{error.message} Backend'in 8000 portunda çalıştığından emin olun.</p>
            </div>
          </CardContent>
        </Card>
      )}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="İstatistikler">
        <StatCard
          label="Takip Edilen Yayıncı"
          value={stats?.tracked_streamers ?? null}
          hint="Aktif yayıncı sayısı"
          icon={Users}
          loading={initialLoading}
        />
        <StatCard
          label="Aktif Yayın"
          value={stats?.active_streams ?? null}
          hint="Şu an kaydedilen yayınlar"
          icon={Radio}
          loading={initialLoading}
        />
        <StatCard
          label="Toplam Kayıt"
          value={stats?.total_recordings ?? null}
          hint="Tüm kayıt oturumları"
          icon={Film}
          loading={initialLoading}
        />
        <StatCard
          label="Hazırlanan Kesit"
          value={stats?.prepared_clips ?? null}
          hint="Hazır ve onaylı kesitler"
          icon={Scissors}
          loading={initialLoading}
        />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="min-w-0 lg:col-span-3">
          <RecentActivityCard items={data?.recent_activity ?? null} loading={loading} />
        </div>
        <div className="min-w-0 lg:col-span-2">
          <SystemStatusCard status={data?.system_status ?? null} loading={loading} />
        </div>
      </section>
    </div>
  );
}
