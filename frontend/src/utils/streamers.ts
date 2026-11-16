import type { StreamPlatform } from "@/types/api";

export const PLATFORM_OPTIONS: { value: StreamPlatform; label: string; placeholder: string }[] = [
  { value: "twitch", label: "Twitch", placeholder: "https://twitch.tv/kanaladi" },
  { value: "youtube", label: "YouTube", placeholder: "https://youtube.com/@kanaladi" },
  { value: "kick", label: "Kick", placeholder: "https://kick.com/kanaladi" },
  { value: "other", label: "Diğer", placeholder: "https://ornek.com/kanal" },
];

export const PLATFORM_LABEL: Record<StreamPlatform, string> = Object.fromEntries(
  PLATFORM_OPTIONS.map((o) => [o.value, o.label]),
) as Record<StreamPlatform, string>;

/** Tailwind classes per platform (brand-tinted chips, no logos). */
export const PLATFORM_CLASS: Record<StreamPlatform, string> = {
  twitch: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  youtube: "border-red-500/30 bg-red-500/10 text-red-300",
  kick: "border-lime-500/30 bg-lime-500/10 text-lime-300",
  other: "border-border bg-muted text-muted-foreground",
};

/** Display a channel URL without the scheme, e.g. "twitch.tv/foo". */
export function shortUrl(url: string): string {
  return url.replace(/^https?:\/\//, "");
}
