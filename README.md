# Streamer AI Engine

İzin verilen yayıncıların canlı yayınlarını belirlenen saatlerde takip eden, kaydeden, yerel yapay zekâ ile önemli anları tespit edip kısa kesitler üreten ve YouTube'a planlı yükleyen modüler otomasyon sistemi.

> **Durum: v0.1.0 — Temel altyapı.** Şu an çalışan kısımlar: backend iskeleti, veritabanı modelleri, health check, Genel Bakış paneli, WebSocket olay kanalı ve AI servis arayüzleri. Yayın takibi, kayıt, AI analizi, video kesme ve YouTube yükleme **henüz uygulanmadı** — bkz. [docs/ROADMAP.md](docs/ROADMAP.md).

## İçerik ve izin politikası

Sistem yalnızca **kayıt ve yeniden yayın izni bulunan** kaynaklarla çalışacak şekilde tasarlanmıştır:

- Her yayıncı kaydında `recording_permission_confirmed` alanı vardır ve varsayılanı `false`'tur.
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
| FFmpeg | Sonraki aşamalar | macOS: `brew install ffmpeg` |
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
# {"status":"ok","application":"Streamer AI Engine","version":"0.1.0"}
```

Geliştirmede Vite, `/api` isteklerini (WebSocket dahil) backend'e proxy'ler; bu yüzden frontend'de ek ayar gerekmez.

## Testler

```bash
./scripts/test.sh
```

veya ayrı ayrı: `cd backend && .venv/bin/python -m pytest` · `cd frontend && npm test`.

## Ortam değişkenleri (`backend/.env`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `APP_NAME`, `APP_VERSION` | Streamer AI Engine, 0.1.0 | Health yanıtında görünür |
| `ENVIRONMENT` | development | development / test / production |
| `DEBUG`, `LOG_LEVEL` | false, INFO | Loglar `logs/backend.log` dosyasına da yazılır (rotasyonlu) |
| `CORS_ORIGINS` | localhost:5173 | Virgülle ayrılmış izinli origin listesi |
| `DATABASE_URL` | boş → `storage/database/streamer_ai_engine.db` | SQLAlchemy URL |
| `STORAGE_ROOT`, `LOG_DIR`, `CONFIG_DIR` | boş → proje klasörleri | Yol geçersiz kılma |
| `OLLAMA_BASE_URL`, `OLLAMA_DEFAULT_MODEL` | localhost:11434, qwen2.5:7b | Yerel LLM |
| `WHISPER_MODEL_SIZE`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE` | small, auto, int8 | faster-whisper |
| `FFMPEG_BINARY` | ffmpeg | PATH'teki ffmpeg |
| `SCHEDULER_ENABLED`, `SCHEDULER_TIMEZONE` | true, Europe/Istanbul | APScheduler |
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` | boş | **Gizli.** Google Cloud OAuth istemcisi |
| `YOUTUBE_REDIRECT_URI`, `YOUTUBE_TOKEN_FILE` | …/oauth/callback, `storage/secrets/` | OAuth token Git dışında saklanır |

Frontend (opsiyonel, `frontend/.env`): `VITE_API_BASE_URL` (API farklı origin'de ise), `VITE_BACKEND_URL` (dev proxy hedefi).

**Güvenlik:** `.env` Git'e dahil edilmez. Gizli değerler `SecretStr` olarak tutulur ve loglarda `***REDACTED***` olarak maskelenir. Dosya yolları `resolve_within()` ile depolama klasörü dışına çıkamaz.

## Klasör yapısı

```
streamer-ai-engine/
├── backend/
│   ├── app/
│   │   ├── api/            # routes/ (health, dashboard, events) + dependencies/
│   │   ├── core/           # config, logging, exceptions, paths
│   │   ├── database/       # Base, engine/session, init_db
│   │   ├── models/         # SQLAlchemy modelleri
│   │   ├── schemas/        # Pydantic I/O şemaları
│   │   ├── services/       # streamer/ recorder/ ai/ video/ youtube/ + dashboard_service
│   │   ├── scheduler/      # APScheduler
│   │   ├── websocket/      # bağlantı yöneticisi
│   │   └── main.py
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
