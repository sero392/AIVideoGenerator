import { Construction } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { NavItem } from "@/layouts/navigation";

export function ComingSoonPage({ item }: { item: NavItem }) {
  const Icon = item.icon;
  return (
    <div className="mx-auto max-w-3xl">
      <Card>
        <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
          <div className="bg-primary/10 text-primary flex size-14 items-center justify-center rounded-2xl">
            <Icon className="size-7" />
          </div>
          <div className="space-y-1">
            <h2 className="text-xl font-semibold">{item.label}</h2>
            <p className="text-muted-foreground inline-flex items-center gap-1.5 text-sm">
              <Construction className="size-4" />
              Bu modül henüz geliştirilmedi ({item.phase}).
            </p>
          </div>
          <p className="text-muted-foreground max-w-md text-sm">
            Planlanan geliştirme sırası için <code className="bg-muted rounded px-1">docs/ROADMAP.md</code> dosyasına bakın.
          </p>
          <Button asChild variant="outline" size="sm">
            <Link to="/">Genel Bakış'a dön</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
