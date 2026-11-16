# Streamer AI Engine

İzin verilen yayıncıların canlı yayınlarını belirlenen saatlerde takip eden, kaydeden, yerel yapay zekâ ile önemli anları tespit edip kısa kesitler üreten ve YouTube'a planlı yükleyen modüler otomasyon sistemi.

> **Durum: v0.4.0 — Kayıt sistemi.** Şu an çalışan kısımlar: backend iskeleti, veritabanı modelleri ve Alembic migration'ları, Genel Bakış paneli, **Yayıncı Yönetimi**, **Yayın Takvimi** (haftalık takip, resmi API'lerle canlı yayın kontrolü, bildirimler), **Kayıtlar** (yayıncının verdiği dosyayı içe aktarma, isteğe bağlı canlı kayıt, tarayıcıda izleme), WebSocket olay kanalı ve AI servis arayüzleri. kayıt, AI analizi, video kesme ve YouTube yükleme **henüz uygulanmadı** — bkz. [docs/ROADMAP.md](docs/ROADMAP.md).

## İçerik ve izin politikası

Sistem yalnızca **kayıt ve yeniden yayın izni bulunan** kaynaklarla çalışacak şekilde tasarlanmıştır:

- Her yayıncı kaydında `recording_permission_confirmed` alanı vardır ve varsayılanı `false`'tur. İzin onaylanırken iznin kimden/nasıl alındığı `permission_notes` alanına yazılmak zorundadır; onay zamanı `permission_confirmed_at` olarak saklanır.
- Kayıt servisi başlamadan önce `ensure_recording_permitted()` kontrolü zorunludur; izin onaylanmamış yayın kaydedilmez.
- Platform kullanım koşullarına uygun, resmi API'ler tercih edilecektir.

## Teknolojiler

| Katman | Teknoloji |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2, SQLite |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui, Lucide |
| AI (yerel) | Ollama + Qwen, faster-whisper |
| Video | FFmpeg, OpenCV |
| Otomasyon | APScheduler |
| İletişim | REST (`/api/v1`), WebSocket (`/api/v1/ws/events`) |
| Test | Pytest, Vitest + Testing Library |

## Gereksinimler

| Araç | Zorunlu mu | Not |
|---|---|---|
| Python 3.11+ | Evet | Yoksa `uv` ile kurulabilir (aşağıda) |
| Node.js 20+ ve npm | Evet | v22 ile test edildi |
| FFmpeg | Otomatik | `requirements.txt` içindeki `imageio-ffmpeg` sanal ortama getirir |
| Ollama | Sonraki aşamalar | https://ollama.com — ardından `ollama pull qwen2.5:7b` |
| faster-whisper, OpenCV | Sonraki aşamalar | `pip install -r backend/requirements-ai.txt` |

Eksik opsiyonel bileşenler uygulamayı durdurmaz; panelde **Sistem Durumu** kartında "Hazır değil" olarak görünür.

## Kurulum

```bash
cd streamer-ai-engine
./scripts/setup.sh
```

Betik; Python 3.11+ bulursa `backend/.venv` oluşturur, bağımlılıkları kurar, `backend/.env` dosyasını `.env.example`'dan kopyalar ve frontend paketlerini yükler.

Sistemde Python 3.11+ yoksa (macOS'ta yalnızca 3.9 gelir):

```bash
python3 -m pip install --user uv
~/Library/Python/3.9/bin/uv python install 3.11
```

<details>
<summary>Manuel kurulum</summary>

```bash
# Backend
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env

# Frontend
cd ../frontend
npm install
```
</details>

## Çalıştırma

İki ayrı terminalde:

```bash
./scripts/dev-backend.sh     # http://localhost:8000  (Swagger: /docs)
```

```bash
./scripts/dev-frontend.sh    # http://localhost:5173
```

Eşdeğer komutlar: `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000` ve `cd frontend && npm run dev`.

Kontrol:

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok","application":"Streamer AI Engine","version":"0.4.0"}
```

Geliştirmede Vite, `/api` isteklerini (WebSocket dahil) backend'e proxy'ler; bu yüzden frontend'de ek ayar gerekmez.

## API

Backend çalışırken tüm uç noktalar Swagger'da denenebilir: http://localhost:8000/docs (ReDoc: `/redoc`).

| Uç nokta | Açıklama |
|---|---|
| `GET /api/v1/health` | Sağlık kontrolü |
| `GET /api/v1/dashboard/summary` | Genel Bakış verileri |
| `GET /api/v1/streamers` | Yayıncı listesi (`search`, `platform`, `is_active`, `permission_confirmed`, `limit`, `offset`) |
| `POST /api/v1/streamers` | Yayıncı ekle |
| `GET / PATCH / DELETE /api/v1/streamers/{id}` | Detay, kısmi güncelleme, silme (kaydı olan yayıncı silinemez → pasif yapılır) |
| `POST /api/v1/streamers/import` | `config/streamers.json` dosyasından içe aktar (mevcut kanallar atlanır) |
| `GET / PUT /api/v1/streamers/{id}/schedule` | Haftalık takip aralıkları (PUT tüm listeyi değiştirir) |
| `GET /api/v1/tracking/overview` | Tüm yayıncıların canlı durumu, takvim durumu, platform bağlantıları |
| `POST /api/v1/tracking/streamers/{id}/check` | Takvim ve aralık beklemeden hemen kontrol et |
| `GET /api/v1/tracking/events` | Son canlıya geçiş / yayın bitiş kayıtları |
| `GET /api/v1/recordings` | Kayıt listesi (`streamer_id`, `status`, `source`, sayfalama) |
| `POST /api/v1/recordings/import` | Video dosyası yükle (multipart: `streamer_id`, `file`, `title`) |
| `POST /api/v1/recordings/inbox/scan` | `storage/recordings/inbox/<yayıncı no>/` klasörünü içe aktar |
| `POST /api/v1/recordings/live` · `POST /{id}/stop` | Canlı kaydı başlat / durdur |
| `GET /api/v1/recordings/{id}/file` | Kayıt dosyası (tarayıcıda sarma desteği, Range) |
| `DELETE /api/v1/recordings/{id}` | Kaydı ve dosyasını sil |
| `GET /api/v1/recordings/system` | FFmpeg / yt-dlp / disk durumu |
| `WS /api/v1/ws/events` | Canlı olay kanalı (`stream.went_live`, `stream.went_offline`, `tracking.updated`, `heartbeat`) |

## Yayın takibi ve platform anahtarları

Yayıncılar yalnızca **Yayın Takvimi** sayfasında belirlediğiniz haftalık saat aralıklarında kontrol edilir (saat dilimi: `SCHEDULER_TIMEZONE`). Canlı yayın durumu yalnızca platformların **resmi API'leri** ile, sizin uygulama anahtarlarınızla sorgulanır; sayfa kazıma yapılmaz, yayın içeriği indirilmez. Anahtarı olmayan platformlar panelde "Anahtar gerekli" olarak görünür, sistem çalışmaya devam eder.

| Platform | `backend/.env` | Nereden alınır | Kontrol aralığı |
|---|---|---|---|
| YouTube | `YOUTUBE_API_KEY` | Google Cloud Console → "YouTube Data API v3"ü etkinleştir → Credentials → API key | 5 dk (`YOUTUBE_POLL_INTERVAL_SECONDS`) |
| Twitch | `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` | https://dev.twitch.tv/console → Register Your Application | 2 dk |
| Kick | `KICK_CLIENT_ID`, `KICK_CLIENT_SECRET` | https://kick.com/settings/developer → uygulama oluştur | 2 dk |

Anahtarı ekledikten sonra backend'i yeniden başlatın. YouTube kontrolü kotayı korumak için `search.list` (100 birim) yerine kanalın herkese açık akışını + `videos.list` (1 birim) kullanır: kanal başına 5 dakikalık kontrol günde yaklaşık 290 birim harcar (varsayılan günlük kota 10.000).

> **Doğrulama notu:** YouTube bağdaştırıcısı gerçek API'ye karşı doğrulandı (16.11.2026): kanal kimliği çözümleme, çevrimdışı kanal ve 7/24 canlı bir kanalda başlık/izleyici/başlangıç tespiti; sonuçlar YouTube'un kendi canlı yayın aramasıyla karşılaştırıldı. Twitch ve Kick API'lerine geliştirme ağından erişilemediği için bu iki bağdaştırıcı yalnızca sahte HTTP yanıtlarıyla test edildi; Kick yanıt alanları resmi şemaya karşı henüz doğrulanmadı.
>
> **YouTube sınırlaması:** Canlılık, kanalın son ~15 videosu üzerinden kontrol edilir (yeni başlayan yayınlar her zaman bu listede olur). Bir kez canlı görülen yayın, listeden düşse bile takip edilmeye devam eder. Sistem başlatılmadan çok önce başlamış ve arkasından 15'ten fazla video yüklenmiş çok uzun (7/24) yayınlar ise fark edilmeyebilir.

## Kayıtlar

İki yol vardır; ikisi de yalnızca **kayıt izni onaylanmış** yayıncılar için çalışır:

| Yol | Nasıl | Varsayılan |
|---|---|---|
| **İçe aktarma** (önerilen) | Yayıncının kendi kaydı (ör. YouTube Studio'dan indirdiği yayın). Kayıtlar → "Dosya yükle" ya da dosyaları `storage/recordings/inbox/<yayıncı no>/` klasörüne koyup "Gelen kutusunu tara". | Her zaman açık |
| **Canlı kayıt** | Yayıncı takvimdeyken canlıya geçince yt-dlp + FFmpeg ile otomatik kaydedilir; yayın bitince kendiliğinden tamamlanır. Yayın Takvimi'nden elle de başlatılabilir. | **Kapalı.** Yayıncı başına "Canlı yayını otomatik kaydet" ile açılır |

> ⚠️ **Canlı kayıt ve kullanım koşulları:** YouTube ve Twitch kullanım koşulları, platformun yazılı izni olmadan içerik indirmeyi yasaklar; yayıncının izni bu maddeyi karşılamaz. Canlı kayıt bu yüzden varsayılan olarak kapalıdır ve riski operatöre aittir. Kullanım koşullarına tam uyumlu yol, yayıncının kendi kaydını içe aktarmaktır.

- Dosyalar `storage/recordings/<yayıncı>-<no>/` altına **yeniden kodlama yapılmadan** MP4'e dönüştürülerek kaydedilir (kalite kaybı yok, tarayıcıda izlenebilir). Dönüştürülemeyen codec'lerde orijinal dosya korunur.
- Güvenlik sınırları: aynı anda en fazla `RECORDING_MAX_CONCURRENT` kayıt, kayıt başına en fazla `RECORDING_MAX_HOURS` saat, boş disk `RECORDING_MIN_FREE_GB`'nin altındaysa canlı kayıt başlamaz, yükleme sınırı `RECORDING_MAX_UPLOAD_GB`.
- Elle durdurulan yayın otomatik olarak yeniden başlatılmaz; hata veren bir yayın en fazla 3 kez yeniden denenir.
- Backend kapanırken devam eden kayıtlar düzgünce durdurulur; çökme sonrası açılışta yarım kalan kayıtlar kurtarılır (kaydedilen kısım korunur).
- FFmpeg sisteme kurulmaz: `imageio-ffmpeg` paketi, sanal ortamın içine hazır bir FFmpeg getirir. Sistemde FFmpeg kuruluysa o kullanılır.

> **Doğrulama notu (v0.4.0):** İçe aktarma, MP4'e dönüştürme, tarayıcıda oynatma/sarma ve silme gerçek backend'de denendi. Canlı kayıt yaşam döngüsü (başlatma, yayın bitince tamamlanma, elle/zaman aşımı/kapanışla durdurma, kurtarma, yeniden deneme sınırı) gerçek FFmpeg süreçleriyle test edildi. **Gerçek bir YouTube canlı yayınından kayıt doğrulandı (16.11.2026):** 1080×1920 / 60 fps, yaklaşık 4 Mbit/sn; kayıt sırasında dosya MPEG-TS (çökmeye dayanıklı), durdurulunca kayıpsız MP4'e dönüştü ve tarayıcıda oynatılıp sarılabildi. Twitch ve Kick için canlı kayıt bu ağdan denenemedi.

## Veritabanı migration'ları

Şema Alembic ile yönetilir; backend açılışta `upgrade head` çalıştırır, elle bir şey yapmanız gerekmez. Model değiştirdiğinizde:

```bash
cd backend
.venv/bin/alembic revision --autogenerate -m "değişiklik açıklaması"
.venv/bin/alembic upgrade head
```

`tests/test_migrations.py`, migration'ların modellerle birebir aynı olduğunu kontrol eder; migration üretmeyi unutursanız test başarısız olur.

Migration'lar SQLite yabancı anahtar denetimini geçici olarak kapatarak çalışır. SQLite bir sütunu değiştirmek için tabloyu yeniden kurar (kopyala + eskisini sil); denetim açıkken bu silme, bağlı satırları (takvim, durum, olay, kayıt) zincirleme siler. Bu durumu `test_downgrade_and_upgrade_keep_child_rows` testi kontrol eder.

## Testler

```bash
./scripts/test.sh
```

veya ayrı ayrı: `cd backend && .venv/bin/python -m pytest` · `cd frontend && npm test`.

## Ortam değişkenleri (`backend/.env`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `APP_NAME`, `APP_VERSION` | Streamer AI Engine, 0.4.0 | Health yanıtında görünür |
| `ENVIRONMENT` | development | development / test / production |
| `DEBUG`, `LOG_LEVEL` | false, INFO | Loglar `logs/backend.log` dosyasına da yazılır (rotasyonlu) |
| `CORS_ORIGINS` | localhost:5173 | Virgülle ayrılmış izinli origin listesi |
| `DATABASE_URL` | boş → `storage/database/streamer_ai_engine.db` | SQLAlchemy URL |
| `STORAGE_ROOT`, `LOG_DIR`, `CONFIG_DIR` | boş → proje klasörleri | Yol geçersiz kılma |
| `OLLAMA_BASE_URL`, `OLLAMA_DEFAULT_MODEL` | localhost:11434, qwen2.5:7b | Yerel LLM |
| `WHISPER_MODEL_SIZE`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE` | small, auto, int8 | faster-whisper |
| `FFMPEG_BINARY` | ffmpeg | PATH'teki FFmpeg, yoksa sanal ortamdaki kopya |
| `RECORDING_MAX_CONCURRENT`, `RECORDING_MAX_HOURS` | 2, 12 | Canlı kayıt sınırları |
| `RECORDING_MIN_FREE_GB`, `RECORDING_MAX_UPLOAD_GB` | 5, 20 | Disk ve yükleme sınırları |
| `RECORDING_FORMAT_SORT` | res:1080 | Canlı kayıt kalitesi (en fazla 1080p) |
| `SCHEDULER_ENABLED`, `SCHEDULER_TIMEZONE` | true, Europe/Istanbul | APScheduler; takvim saatleri bu saat diliminde |
| `TRACKING_ENABLED`, `TRACKING_TICK_SECONDS` | true, 60 | Otomatik canlı yayın kontrolü ve tur sıklığı |
| `YOUTUBE_API_KEY`, `TWITCH_CLIENT_ID/SECRET`, `KICK_CLIENT_ID/SECRET` | boş | **Gizli.** Platform API anahtarları (yukarıdaki tablo) |
| `*_POLL_INTERVAL_SECONDS` | YouTube 300, Twitch/Kick 120 | Platform başına kontrol aralığı |
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` | boş | **Gizli.** Google Cloud OAuth istemcisi |
| `YOUTUBE_REDIRECT_URI`, `YOUTUBE_TOKEN_FILE` | …/oauth/callback, `storage/secrets/` | OAuth token Git dışında saklanır |

Frontend (opsiyonel, `frontend/.env`): `VITE_API_BASE_URL` (API farklı origin'de ise), `VITE_BACKEND_URL` (dev proxy hedefi).

**Güvenlik:** `.env` Git'e dahil edilmez. Gizli değerler `SecretStr` olarak tutulur ve loglarda `***REDACTED***` olarak maskelenir. Dosya yolları `resolve_within()` ile depolama klasörü dışına çıkamaz.

## Klasör yapısı

```
streamer-ai-engine/
├── backend/
│   ├── app/
│   │   ├── api/            # routes/ (health, dashboard, streamers, events) + dependencies/
│   │   ├── core/           # config, logging, exceptions, paths
│   │   ├── database/       # Base, engine/session, init_db
│   │   ├── models/         # SQLAlchemy modelleri
│   │   ├── schemas/        # Pydantic I/O şemaları
│   │   ├── services/       # streamer/ recorder/ ai/ video/ youtube/ + dashboard_service
│   │   ├── scheduler/      # APScheduler
│   │   ├── websocket/      # bağlantı yöneticisi
│   │   └── main.py
│   ├── migrations/         # Alembic migration'ları
│   ├── tests/
│   ├── requirements.txt        # çekirdek
│   ├── requirements-ai.txt     # faster-whisper, opencv (opsiyonel, ağır)
│   └── .env.example
├── frontend/
│   └── src/  components/ pages/ layouts/ hooks/ services/ types/ utils/ lib/ test/
├── ai-models/              # yerel model dosyaları (Git dışı)
├── storage/                # recordings/ clips/ published/ thumbnails/ database/
├── config/                 # settings.json, streamers.json (gizli bilgi içermez)
├── scripts/                # setup, dev-backend, dev-frontend, test
├── docs/                   # ARCHITECTURE.md, ROADMAP.md
├── logs/
└── docker-compose.yml
```

Ayrıntılar: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Docker (doğrulanmadı)

`docker compose up --build` için `docker-compose.yml` ve Dockerfile'lar hazır, ancak bu makinede Docker kurulu olmadığından henüz test edilmedi. Test edilmiş yol yukarıdaki yerel kurulumdur.
