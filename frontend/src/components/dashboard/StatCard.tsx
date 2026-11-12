import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/utils/format";

interface StatCardProps {
  label: string;
  value: number | null;
  hint: string;
  icon: LucideIcon;
  loading?: boolean;
}

export function StatCard({ label, value, hint, icon: Icon, loading }: StatCardProps) {
  return (
    <Card className="gap-0 py-5">
      <CardContent className="flex items-start justify-between gap-4 px-5">
        <div className="min-w-0 space-y-2">
          <p className="text-muted-foreground text-sm font-medium">{label}</p>
          {loading ? (
            <Skeleton className="h-9 w-16" />
          ) : (
            <p className="text-3xl font-semibold tracking-tight tabular-nums" data-testid={`stat-${label}`}>
              {value === null ? "—" : formatNumber(value)}
            </p>
          )}
          <p className="text-muted-foreground text-xs">{hint}</p>
        </div>
        <div className="bg-primary/10 text-primary flex size-10 shrink-0 items-center justify-center rounded-lg">
          <Icon className="size-5" />
        </div>
      </CardContent>
    </Card>
  );
}
