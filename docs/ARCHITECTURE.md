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
| `services/streamer` | Arayüz | `StreamPlatformAdapter` ABC, `ensure_recording_permitted()` izin kapısı |
| `services/recorder` | Arayüz | `StreamRecorder` ABC (start/stop) |
| `services/video` | Arayüz | `VideoProcessor` ABC (cut, extract_audio, thumbnail), ffmpeg/opencv varlık kontrolü |
| `services/youtube` | Arayüz | `YouTubePublisher` ABC, `UploadRequest` |
| `services/dashboard_service` | Çalışıyor | Panel istatistikleri (gerçek DB sayımları), son işlemler, bileşen durumları |

### Yapay zekâ ilkeleri

- Çalışma zamanında **yerel ve ücretsiz** modeller (Ollama/Qwen, faster-whisper). Claude yalnızca geliştirme sürecinde kullanılır; uygulama Claude API'ye bağımlı değildir.
- Yeni sağlayıcı eklemek: ilgili ABC'yi uygula → `AIProviderRegistry._build_llm` içine ekle → `config/settings.json`'da etkinleştir.
- Ağır paketler (`faster-whisper`, `opencv`) opsiyoneldir ve tembel (lazy) yüklenir; yoksa backend yine açılır.

## Veri modeli

```
Streamer 1───* RecordingSession 1───* Clip 1───* YoutubeVideo
   └────────────────1───*───────────────┘
AIModel        SystemSetting     (bağımsız tablolar)
```

| Tablo | Önemli alanlar | Not |
|---|---|---|
| `streamers` | name, platform, channel_url (unique), is_active, **recording_permission_confirmed**, permission_notes | İzin alanı varsayılan `false` |
| `recording_sessions` | streamer_id, started_at, ended_at, file_path, status | `file_path` depolama köküne göreli |
| `clips` | streamer_id, recording_id, title, start_time, end_time, file_path, ai_score, status | `end_time > start_time`, `ai_score ∈ [0,1]` kısıtları |
| `youtube_videos` | clip_id, youtube_video_id (unique), title, scheduled_at, published_at, status | |
| `ai_models` | name, provider, model_identifier, is_active, configuration (JSON) | (provider, model_identifier) benzersiz |
| `system_settings` | setting_key (unique), setting_value | Gizli değerler burada tutulmaz |

Tüm tablolarda `created_at` (system_settings'te `updated_at`) vardır. Silmeler kaskad çalışır (SQLite'ta `PRAGMA foreign_keys=ON`). Enum'lar native DB enum yerine string olarak saklanır.

**Migration'a geçiş:** Şimdilik tablolar açılışta `Base.metadata.create_all()` ile oluşturulur. Şema değişmeye başladığında: `alembic init`, `target_metadata = Base.metadata` (önce `import app.models`), ilk revizyonu `--autogenerate` ile üret ve `init_db` yerine `alembic upgrade head` çalıştır. İsimlendirme kuralı sayesinde constraint adları sabittir.

## Frontend

| Klasör | Sorumluluk |
|---|---|
| `layouts/` | `AppLayout` (sabit sidebar + header), `navigation.ts` (menü tanımı; `phase` alanı olan sayfalar "yakında" sayfasına yönlenir) |
| `pages/` | `OverviewPage` (çalışıyor), `ComingSoonPage` (diğer modüller) |
| `components/ui` | shadcn/ui bileşenleri (card, badge, button, separator, skeleton) |
| `components/dashboard` | İstatistik, son işlemler ve sistem durumu kartları |
| `services/api.ts` | Tipli API istemcisi, `ApiError` |
| `hooks/` | `useApiQuery` (iptal + periyodik yenileme), `useEventSocket` (otomatik yeniden bağlanan WebSocket) |
| `types/api.ts` | Backend şemalarının TS karşılıkları |

Panel veri yokken sahte rakam göstermez: backend erişilemezse "—" ve hata kartı, boş DB'de gerçek `0` gösterir.

## Güvenlik

- Gizli bilgiler yalnızca `backend/.env`'de; `SecretStr` ile `repr`/log dışı tutulur. Log filtresi `token=`, `client_secret=`, `Bearer …` gibi kalıpları maskeler.
- `config/*.json` gizli bilgi içermez; YouTube refresh token'ı `storage/secrets/` altında (Git dışı) saklanacak.
- Dosya yolları `resolve_within()` ile depolama klasörüne hapsedilir; `..` ve mutlak yollar reddedilir. Dosya adları `sanitize_filename()` ile temizlenir.
- Girdi doğrulaması Pydantic şemalarıyla (ör. `StreamerCreate`: yalnızca https kanal URL'si, geçerli platform).
- CORS yalnızca `CORS_ORIGINS` listesine izin verir.
