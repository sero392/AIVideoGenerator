# Mimari

## Genel akış (hedef)

```
 Zamanlayıcı ──► Yayın Takibi ──► İzin Kontrolü ──► Kayıt ──► AI Analizi ──► Kesit ──► Düzenleme ──► YouTube
 (APScheduler)   (platform        (ensure_recording  (FFmpeg)  (Whisper +    (FFmpeg)  (FFmpeg/     (Data API,
                  adaptörleri)     _permitted)                   Qwen)                   OpenCV)      planlı)
                                                   │
                         SQLite (durum) ◄──────────┴──────────► WebSocket olayları ──► React panel
```

v0.1.0'da bu akışın yalnızca iskeleti vardır: arayüzler, veri modeli, panel ve olay kanalı. Her ok, [ROADMAP](ROADMAP.md)'teki bir aşamaya karşılık gelir.

## Backend katmanları

| Katman | Klasör | Sorumluluk |
|---|---|---|
| API | `app/api/routes` | HTTP/WebSocket uç noktaları. İnce tutulur; iş mantığı servislerde. Tüm rotalar `/api/v1` altında (`app/api/router.py`). Yeni sürüm = yeni router. |
| Bağımlılıklar | `app/api/dependencies` | `DbSession`, `AppSettings` gibi FastAPI `Depends` kısayolları |
| Çekirdek | `app/core` | `config` (pydantic-settings, `.env`), `logging` (konsol + dönen dosya, gizli bilgi maskeleme), `exceptions` (tek tip hata zarfı), `paths` (güvenli dosya yolu) |
| Veritabanı | `app/database` | Declarative `Base` (Alembic uyumlu isimlendirme kuralı), engine/session fabrikası, `init_db` |
| Modeller | `app/models` | SQLAlchemy 2 tipli modeller ve durum enum'ları |
| Şemalar | `app/schemas` | Pydantic giriş/çıkış modelleri ve doğrulama kuralları |
| Servisler | `app/services/*` | İş mantığı; her alan kendi alt paketinde, soyut arayüz + somut uygulama |
| Zamanlayıcı | `app/scheduler` | APScheduler `AsyncIOScheduler`; şimdilik yalnızca 30 sn'lik heartbeat |
| WebSocket | `app/websocket` | Bağlı istemcilere olay yayını (`ConnectionManager`) |

### Hata yönetimi

Tüm hatalar aynı biçimde döner:

```json
{ "error": { "code": "not_found", "message": "...", "details": null } }
```

`AppError` alt sınıfları (`NotFoundError`, `ConflictError`, `UnsafePathError`, `RecordingNotPermittedError`, `ServiceUnavailableError`) kendi HTTP kodunu taşır. Beklenmeyen hatalar loglanır, istemciye yalnızca genel mesaj gider.

### Servis modülleri

| Modül | Durum | İçerik |
|---|---|---|
| `services/ai` | Arayüz + bağlantı | `LLMProvider`, `TranscriptionProvider` ABC'leri; `OllamaProvider` (sağlık, model listesi, `generate`); `FasterWhisperProvider` (kurulum kontrolü, `transcribe` henüz yok); `AIProviderRegistry` (modeli `.env` + `config/settings.json`'dan seçer) |
| `services/streamer` | Çalışıyor | `streamer_service`: CRUD, iş kuralları, JSON içe aktarma · `channel_url`: adres doğrulama/normalleştirme · `schedule`: saf haftalık takvim mantığı · `tracking_service`: `Tracker` kontrol döngüsü · `tracking_query`: genel durum, olaylar, takvim kaydetme · `platforms/`: Twitch, YouTube, Kick bağdaştırıcıları · `base.ensure_recording_permitted()` izin kapısı |
| `services/recorder` | Çalışıyor | `manager`: canlı kayıt süreçleri (başlat/durdur/izle/sonlandır, otomatik eşitleme, kurtarma, kapanış) · `importer`: yükleme + gelen kutusu · `storage`: dosya yolları ve benzersiz adlar · `recording_query`: listeleme, silme, sistem bilgisi |
| `services/video` | Kısmen | FFmpeg bulma (sistem → paket içi), `probe` (süre/çözünürlük), `remux_to_mp4` (kayıpsız). `VideoProcessor` ABC (kesme/düzenleme Aşama 7–8) |
| `services/youtube` | Arayüz | `YouTubePublisher` ABC, `UploadRequest` |
| `services/dashboard_service` | Çalışıyor | Panel istatistikleri (gerçek DB sayımları), son işlemler, bileşen durumları |

### Yapay zekâ ilkeleri

- Çalışma zamanında **yerel ve ücretsiz** modeller (Ollama/Qwen, faster-whisper). Claude yalnızca geliştirme sürecinde kullanılır; uygulama Claude API'ye bağımlı değildir.
- Yeni sağlayıcı eklemek: ilgili ABC'yi uygula → `AIProviderRegistry._build_llm` içine ekle → `config/settings.json`'da etkinleştir.
- Ağır paketler (`faster-whisper`, `opencv`) opsiyoneldir ve tembel (lazy) yüklenir; yoksa backend yine açılır.

## Yayın takibi

```
APScheduler (her TRACKING_TICK_SECONDS) ──► Tracker.run_cycle()
   for each streamer:
     pasif?            → state = inactive
     takvim dışı?      → state = outside_schedule
     platform yok?     → unsupported   ·  anahtar yok? → not_configured
     aralık dolmadı?   → atla (son sonuç geçerli)
     aksi halde        → platforma göre grupla ──► adapter.check(batch)
   sonuç → stream_statuses (live/offline/error)
   olay günlüğüne göre geçiş → stream_events (went_live / went_offline)
   WebSocket: stream.went_live | stream.went_offline | tracking.updated
```

- **Takvim:** `tracking_windows` (gün 0=Pzt…6=Paz, `HH:MM`–`HH:MM`, `SCHEDULER_TIMEZONE`). Bitiş ≤ başlangıç ise gece yarısını geçer, eşitse 24 saat. Takvimi olmayan yayıncı otomatik kontrol edilmez; "Şimdi kontrol et" takvim ve aralığı yok sayar.
- **Geçiş tespiti** son olay kaydına göre yapılır; araya hata ya da takvim dışı dönem girse bile çift "canlıya geçti" olayı oluşmaz.
- **Bağdaştırıcılar** (`PlatformAdapter`): toplu sorgu (Twitch 100, Kick 50, YouTube 50 video/istek), uygulama token'ı bellekte önbelleklenir, 401'de yenilenir. HTTP hataları yanıt gövdesi içermeyen kullanıcı mesajlarına çevrilir (gövde token içerebilir). Bir bağdaştırıcıdaki beklenmeyen hata diğer platformları durdurmaz.
- **YouTube:** kanal kimliği bir kez `channels.list` (forHandle) ile çözülür ve `streamers.platform_channel_id`'de saklanır; canlılık kanalın Atom akışındaki son 5 video için `videos.list` ile kontrol edilir (kota dostu). Kanal adresi değişince önbellek ve durum sıfırlanır.
- **Gizlilik:** API anahtarları URL'de gittiği için `httpx` logları WARNING seviyesine çekildi ve log filtresi `?key=` parametrelerini maskeler.
- **Eşzamanlılık:** zamanlayıcı turu ve elle kontrol aynı `asyncio.Lock` ile sıraya girer.

## Kayıt sistemi

```
Tracker turu ──► RecordingManager.sync_with_tracking()
   canlı + izinli + live_capture_enabled + aktif kayıt yok
   + elle durdurulmamış + <3 hata + 2 dk bekleme  ──► start_live()
        güvenlik: izin, eşzamanlı sınır, boş disk, FFmpeg
        yt-dlp -S res:1080 -f bv*+ba/b --hls-use-mpegts  →  <taban>.ts  (+ .log)
   OFFLINE olunca ──► stop(stream_ended)
_watch: süreç biter / azami süre dolar ──► _finalize
   .ts → MP4 (kayıpsız, faststart) — olmazsa orijinal korunur → probe (süre) → COMPLETED / FAILED
İçe aktarma: yükleme (parça parça, boyut sınırı) veya inbox/<yayıncı no>/ → probe → MP4 → COMPLETED
```

- `recording_sessions.stop_reason`: `manual` | `stream_ended` | `max_duration` | `shutdown` | `error`. `manual` olan bir yayın (aynı `platform_stream_id`) otomatik olarak yeniden kaydedilmez.
- Dosya adları `<YYYYmmdd-HHMMSS>-<kayıt no>`; aynı adda dosya varsa ek alır. SQLite silinen son satırın numarasını yeniden verebilir; kayıt aracı başka bir kaydın dosyasını görmemeli.
- Kapanışta tüm kayıtlara SIGINT gönderilir (yt-dlp/FFmpeg dosyayı düzgün kapatır), 30 sn sonra zorla sonlandırılır. Açılışta `RECORDING/PROCESSING` durumunda kalmış oturumlar kurtarılır.
- WebSocket: `recording.started`, `recording.processing`, `recording.finished`.

## Veri modeli

```
Streamer 1───* RecordingSession 1───* Clip 1───* YoutubeVideo
   └────────────────1───*───────────────┘
AIModel        SystemSetting     (bağımsız tablolar)
```

| Tablo | Önemli alanlar | Not |
|---|---|---|
| `streamers` | name, platform, channel_url (unique, normalleştirilmiş), is_active, **recording_permission_confirmed**, permission_notes, permission_confirmed_at, updated_at | İzin varsayılan `false`; onaylıysa not zorunlu |
| `recording_sessions` | streamer_id, source (live_capture/import), title, platform_stream_id, started_at, ended_at, file_path, duration_seconds, file_size_bytes, status, stop_reason, error_message | `file_path` `storage/recordings`'e göreli |
| `clips` | streamer_id, recording_id, title, start_time, end_time, file_path, ai_score, status | `end_time > start_time`, `ai_score ∈ [0,1]` kısıtları |
| `tracking_windows` | streamer_id, day_of_week, start_time, end_time | Haftalık takip aralıkları |
| `stream_statuses` | streamer_id (PK), state, title, viewer_count, live_started_at, stream_url, error_message, checked_at, state_changed_at | Yayıncı başına son canlı durum |
| `stream_events` | streamer_id, event_type (went_live/went_offline), title, occurred_at | Geçiş günlüğü (Aşama 3 kayıt tetikleyicisi) |
| `youtube_videos` | clip_id, youtube_video_id (unique), title, scheduled_at, published_at, status | |
| `ai_models` | name, provider, model_identifier, is_active, configuration (JSON) | (provider, model_identifier) benzersiz |
| `system_settings` | setting_key (unique), setting_value | Gizli değerler burada tutulmaz |

Tüm tablolarda `created_at` (system_settings'te `updated_at`) vardır. Silmeler kaskad çalışır (SQLite'ta `PRAGMA foreign_keys=ON`). Enum'lar native DB enum yerine string olarak saklanır.

**Migration'lar (Alembic):** `backend/migrations/versions/` altında. `init_db` açılışta `upgrade head` çalıştırır. v0.1.0'da `create_all` ile oluşturulmuş (alembic_version tablosu olmayan) veritabanları otomatik olarak `0001` başlangıç revizyonuyla işaretlenip yükseltilir; veriler korunur. Veritabanı adresi `alembic.ini`'de değil, uygulama ayarlarından okunur. SQLite için `render_as_batch=True` kullanılır. `test_migrations.py` modeller ile migration'ların farkını ve eski veritabanı yükseltmesini test eder.

| Revizyon | İçerik |
|---|---|
| `0001` | Başlangıç şeması (v0.1.0) |
| `0002` | `streamers.permission_confirmed_at`, `streamers.updated_at` |
| `0003` | `tracking_windows`, `stream_statuses`, `stream_events`, `streamers.platform_channel_id` |
| `0004` | `recording_sessions`: source, title, source_url, platform_stream_id, duration_seconds, file_size_bytes, error_message, stop_reason, updated_at · `streamers.live_capture_enabled` |

## Frontend

| Klasör | Sorumluluk |
|---|---|
| `layouts/` | `AppLayout` (sabit sidebar + header), `navigation.ts` (menü tanımı; `phase` alanı olan sayfalar "yakında" sayfasına yönlenir) |
| `pages/` | `OverviewPage`, `StreamersPage`, `SchedulePage`, `RecordingsPage` (çalışıyor), `ComingSoonPage` (diğer modüller) |
| `components/recordings` | Yükleme (XHR ilerleme çubuğu), oynatıcı, silme onayı |
| `components/schedule` | Haftalık şerit (`WeekStrip`), takvim düzenleyici |
| `services/events.ts` | Tek WebSocket bağlantısından gelen olayları sayfalara dağıtan olay yolu (`useServerEvent`) |
| `components/streamers` | Yayıncı formu, silme onayı, içe aktarma sonucu, platform/izin rozetleri |
| `components/ui` | shadcn/ui bileşenleri (card, badge, button, dialog, input, textarea, label, native-select, switch, checkbox, table, sonner, separator, skeleton) |
| `components/dashboard` | İstatistik, son işlemler ve sistem durumu kartları |
| `services/api.ts` | Tipli API istemcisi, `ApiError` |
| `hooks/` | `useApiQuery` (iptal + periyodik yenileme), `useEventSocket` (otomatik yeniden bağlanan WebSocket) |
| `types/api.ts` | Backend şemalarının TS karşılıkları |

Panel veri yokken sahte rakam göstermez: backend erişilemezse "—" ve hata kartı, boş DB'de gerçek `0` gösterir.

## Güvenlik

- Gizli bilgiler yalnızca `backend/.env`'de; `SecretStr` ile `repr`/log dışı tutulur. Log filtresi `token=`, `client_secret=`, `Bearer …` gibi kalıpları maskeler.
- `config/*.json` gizli bilgi içermez; YouTube refresh token'ı `storage/secrets/` altında (Git dışı) saklanacak.
- Dosya yolları `resolve_within()` ile depolama klasörüne hapsedilir; `..` ve mutlak yollar reddedilir. Dosya adları `sanitize_filename()` ile temizlenir.
- Girdi doğrulaması Pydantic şemalarıyla (bilinmeyen alanlar reddedilir) ve servis katmanındaki iş kurallarıyla: kanal adresi https olmalı ve seçilen platformun alan adıyla eşleşmeli (`evil.twitch.tv.attacker.com` gibi adresler reddedilir), arama ifadelerindeki `%`/`_` karakterleri kaçışlanır.
- CORS yalnızca `CORS_ORIGINS` listesine izin verir.
