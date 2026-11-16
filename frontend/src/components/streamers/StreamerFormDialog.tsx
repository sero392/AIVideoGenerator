import { Loader2, ShieldCheck, Video } from "lucide-react";
import { type FormEvent, useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/services/api";
import type { StreamPlatform, Streamer, StreamerInput } from "@/types/api";
import { PLATFORM_OPTIONS } from "@/utils/streamers";

type FieldErrors = Partial<Record<keyof StreamerInput, string>>;

const EMPTY: StreamerInput = {
  name: "",
  platform: "twitch",
  channel_url: "",
  is_active: true,
  recording_permission_confirmed: false,
  permission_notes: "",
  live_capture_enabled: false,
};

function toInput(s: Streamer): StreamerInput {
  return {
    name: s.name,
    platform: s.platform,
    channel_url: s.channel_url,
    is_active: s.is_active,
    recording_permission_confirmed: s.recording_permission_confirmed,
    permission_notes: s.permission_notes ?? "",
    live_capture_enabled: s.live_capture_enabled,
  };
}

/** Client-side checks for instant feedback; the backend remains the source of truth. */
export function validateStreamer(values: StreamerInput): FieldErrors {
  const errors: FieldErrors = {};
  if (!values.name.trim()) errors.name = "Yayıncı adı zorunludur.";
  else if (values.name.trim().length > 100) errors.name = "En fazla 100 karakter olabilir.";
  const url = values.channel_url.trim();
  if (!url) errors.channel_url = "Kanal adresi zorunludur.";
  else if (!url.startsWith("https://")) errors.channel_url = "Kanal adresi https:// ile başlamalıdır.";
  if (values.recording_permission_confirmed && !values.permission_notes?.trim()) {
    errors.permission_notes = "İzin onaylanırken iznin kimden ve nasıl alındığını yazmalısınız.";
  }
  return errors;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Edit mode when provided, create mode otherwise. */
  streamer?: Streamer | null;
  onSubmit: (input: StreamerInput) => Promise<void>;
}

export function StreamerFormDialog({ open, onOpenChange, streamer, onSubmit }: Props) {
  const [values, setValues] = useState<StreamerInput>(EMPTY);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const id = useId();
  const isEdit = Boolean(streamer);

  useEffect(() => {
    if (open) {
      setValues(streamer ? toInput(streamer) : EMPTY);
      setErrors({});
      setFormError(null);
    }
  }, [open, streamer]);

  const set = <K extends keyof StreamerInput>(key: K, value: StreamerInput[K]) => {
    setValues((v) => ({ ...v, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const clientErrors = validateStreamer(values);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length) return;

    setSubmitting(true);
    setFormError(null);
    try {
      await onSubmit({
        ...values,
        name: values.name.trim(),
        channel_url: values.channel_url.trim(),
        permission_notes: values.permission_notes?.trim() || null,
      });
      onOpenChange(false);
    } catch (err) {
      if (err instanceof ApiError) {
        const fieldErrors = err.fieldErrors as FieldErrors;
        if (err.code === "conflict") fieldErrors.channel_url = err.message;
        setErrors(fieldErrors);
        if (!Object.keys(fieldErrors).length) setFormError(err.message);
      } else {
        setFormError("Beklenmeyen bir hata oluştu.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const placeholder = PLATFORM_OPTIONS.find((o) => o.value === values.platform)?.placeholder;
  const fieldId = (name: string) => `${id}-${name}`;
  const errorText = (name: keyof StreamerInput) =>
    errors[name] ? (
      <p id={fieldId(`${name}-error`)} className="text-destructive text-xs" role="alert">
        {errors[name]}
      </p>
    ) : null;
  const a11y = (name: keyof StreamerInput) => ({
    id: fieldId(name),
    "aria-invalid": Boolean(errors[name]) || undefined,
    "aria-describedby": errors[name] ? fieldId(`${name}-error`) : undefined,
  });

  return (
    <Dialog open={open} onOpenChange={(o) => !submitting && onOpenChange(o)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Yayıncıyı Düzenle" : "Yeni Yayıncı"}</DialogTitle>
          <DialogDescription>
            Yalnızca içeriğini kaydetme ve yeniden yayınlama izni aldığınız yayıncıları ekleyin.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor={fieldId("name")}>Yayıncı adı</Label>
            <Input
              {...a11y("name")}
              value={values.name}
              onChange={(e) => set("name", e.target.value)}
              maxLength={100}
              autoFocus
            />
            {errorText("name")}
          </div>

          <div className="grid gap-4 sm:grid-cols-[10rem_1fr]">
            <div className="space-y-2">
              <Label htmlFor={fieldId("platform")}>Platform</Label>
              <NativeSelect
                {...a11y("platform")}
                value={values.platform}
                onChange={(e) => set("platform", e.target.value as StreamPlatform)}
              >
                {PLATFORM_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="min-w-0 space-y-2">
              <Label htmlFor={fieldId("channel_url")}>Kanal adresi</Label>
              <Input
                {...a11y("channel_url")}
                type="url"
                inputMode="url"
                placeholder={placeholder}
                value={values.channel_url}
                onChange={(e) => set("channel_url", e.target.value)}
                maxLength={500}
              />
              {errorText("channel_url")}
            </div>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-3">
            <div>
              <Label htmlFor={fieldId("is_active")}>Takip aktif</Label>
              <p className="text-muted-foreground mt-1 text-xs">Pasif yayıncılar takip edilmez ve kaydedilmez.</p>
            </div>
            <Switch id={fieldId("is_active")} checked={values.is_active} onCheckedChange={(c) => set("is_active", c)} />
          </div>

          <div className="space-y-3 rounded-lg border px-3 py-3">
            <div className="flex items-start gap-3">
              <Checkbox
                id={fieldId("recording_permission_confirmed")}
                checked={values.recording_permission_confirmed}
                onCheckedChange={(c) => {
                  set("recording_permission_confirmed", c === true);
                  if (c !== true) set("live_capture_enabled", false); // capture needs permission
                }}
                className="mt-0.5"
              />
              <div className="space-y-1">
                <Label htmlFor={fieldId("recording_permission_confirmed")} className="leading-snug">
                  <ShieldCheck className="text-success size-4" />
                  Kayıt ve yeniden yayın izni alındı
                </Label>
                <p className="text-muted-foreground text-xs">
                  İzin onaylanmadan sistem bu yayıncının hiçbir yayınını kaydetmez. Platformun kullanım koşullarını da
                  kontrol edin.
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor={fieldId("permission_notes")}>
                İzin notları
                {values.recording_permission_confirmed && <span className="text-destructive">*</span>}
              </Label>
              <Textarea
                {...a11y("permission_notes")}
                placeholder="Örn: 10.11.2026 tarihinde e-posta ile yazılı izin verdi, sözleşme Drive'da."
                value={values.permission_notes ?? ""}
                onChange={(e) => set("permission_notes", e.target.value)}
                maxLength={2000}
                rows={3}
              />
              {errorText("permission_notes")}
            </div>
          </div>

          <div className="space-y-2 rounded-lg border px-3 py-3">
            <div className="flex items-center justify-between gap-4">
              <div>
                <Label htmlFor={fieldId("live_capture_enabled")}>
                  <Video className="size-4" />
                  Canlı yayını otomatik kaydet
                </Label>
                <p className="text-muted-foreground mt-1 text-xs">
                  Yayıncı takvimdeyken canlıya geçince kayıt kendiliğinden başlar.
                </p>
              </div>
              <Switch
                id={fieldId("live_capture_enabled")}
                checked={values.live_capture_enabled}
                disabled={!values.recording_permission_confirmed}
                onCheckedChange={(c) => set("live_capture_enabled", c)}
              />
            </div>
            {!values.recording_permission_confirmed ? (
              <p className="text-muted-foreground text-xs">Önce kayıt iznini onaylayın.</p>
            ) : (
              values.live_capture_enabled && (
                <p className="text-warning text-xs" role="note">
                  Canlı kayıt platformun oynatıcısı dışında indirme yapar. YouTube ve Twitch kullanım koşulları
                  platformun yazılı izni olmadan indirmeyi yasaklar; yayıncının izni bu maddeyi karşılamaz. Risk size
                  aittir. Daha güvenli yol: yayıncının kendi kaydını Kayıtlar sayfasından içe aktarmak.
                </p>
              )
            )}
            {errorText("live_capture_enabled")}
          </div>

          {formError && (
            <p className="border-destructive/40 bg-destructive/10 text-destructive rounded-md border px-3 py-2 text-sm" role="alert">
              {formError}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting && <Loader2 className="animate-spin" />}
              {isEdit ? "Kaydet" : "Yayıncı Ekle"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
