import { CheckCircle2, CircleAlert, CircleSlash } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { StreamerImportResult } from "@/types/api";
import { shortUrl } from "@/utils/streamers";

interface Props {
  result: StreamerImportResult | null;
  onOpenChange: (open: boolean) => void;
}

export function ImportResultDialog({ result, onOpenChange }: Props) {
  if (!result) return null;
  const { created, skipped, errors } = result;
  const nothing = !created.length && !skipped.length && !errors.length;

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>İçe aktarma sonucu</DialogTitle>
          <DialogDescription>
            <code className="bg-muted rounded px-1">config/streamers.json</code> dosyası işlendi.
          </DialogDescription>
        </DialogHeader>

        {nothing ? (
          <p className="text-muted-foreground text-sm">Dosyada içe aktarılacak yayıncı bulunamadı.</p>
        ) : (
          <div className="space-y-4 text-sm">
            <Section icon={<CheckCircle2 className="text-success size-4" />} title={`Eklendi (${created.length})`}>
              {created.map((s) => (
                <li key={s.id}>
                  {s.name} <span className="text-muted-foreground">— {shortUrl(s.channel_url)}</span>
                </li>
              ))}
            </Section>
            <Section icon={<CircleSlash className="text-muted-foreground size-4" />} title={`Atlandı (${skipped.length})`}>
              {skipped.map((s) => (
                <li key={s.channel_url}>
                  {shortUrl(s.channel_url)} <span className="text-muted-foreground">— {s.reason}</span>
                </li>
              ))}
            </Section>
            <Section icon={<CircleAlert className="text-destructive size-4" />} title={`Hatalı (${errors.length})`}>
              {errors.map((e) => (
                <li key={e.index}>
                  <span className="text-muted-foreground">#{e.index + 1}:</span> {e.message}
                </li>
              ))}
            </Section>
          </div>
        )}

        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Tamam</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode[] }) {
  if (!children.length) return null;
  return (
    <div className="space-y-1.5">
      <p className="flex items-center gap-2 font-medium">
        {icon}
        {title}
      </p>
      <ul className="text-foreground/90 max-h-40 space-y-1 overflow-y-auto pl-6">{children}</ul>
    </div>
  );
}
