# Yol Haritası

## Aşama 0 — Temel altyapı ✅ (v0.1.0)

Proje iskeleti, FastAPI + SQLite, veri modelleri, health check, hata/log altyapısı, Genel Bakış paneli, WebSocket olay kanalı, AI servis arayüzleri, testler.

## Sonraki aşamalar

| # | Aşama | Kapsam | Bağımlılık |
|---|---|---|---|
| 1 | **Yayıncı yönetimi** | CRUD API (`/api/v1/streamers`), izin onayı ve notları, `config/streamers.json` içe aktarma, "Yayıncı Yönetimi" sayfası | — |
| 2 | **Yayın takip sistemi** | Platform adaptörleri (resmi API'ler), yayıncı başına takip takvimi, APScheduler işleri, canlı durum olayları (WebSocket), "Yayın Takvimi" sayfası | 1 |
| 3 | **Video kayıt sistemi** | `StreamRecorder` uygulaması (FFmpeg), izin kapısı zorunlu, disk kotası/temizlik, kayıt durumu takibi, "Kayıtlar" sayfası | 2, FFmpeg |
| 4 | **Qwen entegrasyonu** | Ollama üzerinden prompt şablonları, model yönetimi (`ai_models` tablosu), "AI Model Ayarları" sayfası | Ollama |
| 5 | **Whisper entegrasyonu** | Ses çıkarma + faster-whisper transkripsiyon, zaman damgalı segmentler, arka plan iş kuyruğu | 3, requirements-ai |
| 6 | **Önemli an tespit algoritması** | Transkript (Qwen ile anlamsal skor) + ses enerjisi + sohbet yoğunluğu sinyallerinin birleşimi, `ai_score` | 4, 5 |
| 7 | **Otomatik video kesme** | Skorlu aralıklardan kesit üretimi, min/max süre kuralları, "AI Kesitleri" sayfası (onay/ret) | 6 |
| 8 | **Video düzenleme** | Dikey format (9:16), altyazı yakma, küçük resim üretimi (OpenCV), intro/outro | 7 |
| 9 | **YouTube API entegrasyonu** | OAuth 2.0 akışı, güvenli token saklama, yükleme, kota takibi | — |
| 10 | **Otomatik yayınlama** | Planlı yükleme takvimi, başlık/açıklama/etiket üretimi (Qwen), "YouTube Yönetimi" sayfası | 8, 9 |
| 11 | **Performans analizi** | YouTube Analytics verileri, kesit başarısı ↔ AI skoru karşılaştırması, panelde grafikler | 10 |

## Teknik borç / altyapı notları

- Şema değişmeye başladığında Alembic migration'larına geçiş (bkz. ARCHITECTURE.md).
- Uzun süren işler (transkripsiyon, render) için kalıcı iş kuyruğu (SQLite tabanlı tablo + worker).
- Uç nokta sayısı artınca frontend'de TanStack Query'ye geçiş.
- Kimlik doğrulama (panel tek kullanıcılı olsa da yerel ağa açılmadan önce gerekli).
- Docker compose kurulumunun doğrulanması.
