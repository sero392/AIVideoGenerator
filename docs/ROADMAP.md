# Yol Haritası

## Aşama 0 — Temel altyapı ✅ (v0.1.0)

Proje iskeleti, FastAPI + SQLite, veri modelleri, health check, hata/log altyapısı, Genel Bakış paneli, WebSocket olay kanalı, AI servis arayüzleri, testler.

## Aşama 1 — Yayıncı yönetimi ✅ (v0.2.0)

`/api/v1/streamers` CRUD + filtre/sayfalama, platforma göre kanal adresi doğrulama/normalleştirme, izin onayı için zorunlu not ve onay zamanı, kaydı olan yayıncının silinmesinin engellenmesi, `config/streamers.json` içe aktarma, Yayıncı Yönetimi sayfası (masaüstü tablo + mobil kart), Alembic migration altyapısı.

## Aşama 2 — Yayın takip sistemi ✅ (v0.3.0)

Haftalık takip takvimi (gece yarısını geçen ve 24 saatlik aralıklar), Twitch/YouTube/Kick resmi API bağdaştırıcıları, APScheduler kontrol turu (platform başına aralık), canlı durum + geçiş günlüğü, WebSocket bildirimleri, "Şimdi kontrol et", Yayın Takvimi sayfası. Genel Bakış'taki "Aktif Yayın" artık takipçinin gördüğü canlı yayınları sayar.

Açık kalanlar: Twitch ve Kick bağdaştırıcılarının gerçek API ile doğrulanması (geliştirme ağından erişilemedi), Kick yanıt şemasının resmi OpenAPI'ye karşı kontrolü.

## Aşama 3 — Video kayıt sistemi ✅ (v0.4.0)

İçe aktarma (yükleme + gelen kutusu klasörü), yayıncı başına isteğe bağlı canlı kayıt (yt-dlp + FFmpeg), takip turuyla otomatik başlatma/durdurma, güvenlik sınırları (izin, eşzamanlı kayıt, süre, disk), kayıpsız MP4 dönüştürme, çökme kurtarma, Kayıtlar sayfası (izleme, indirme, silme). Ayrıca migration'larda SQLite yabancı anahtar zincirleme silme hatası düzeltildi.

Açık kalanlar: gerçek bir yayından canlı kayıt denemesi (yayıncı başına açılması gerekir), Twitch/Kick için canlı kayıt denemesi (bu ağdan erişilemiyor).

## Sonraki aşamalar

| # | Aşama | Kapsam | Bağımlılık |
|---|---|---|---|
| 1 | ~~Yayıncı yönetimi~~ ✅ | CRUD API (`/api/v1/streamers`), izin onayı ve notları, `config/streamers.json` içe aktarma, "Yayıncı Yönetimi" sayfası | — |
| 2 | ~~Yayın takip sistemi~~ ✅ | Platform adaptörleri (resmi API'ler), yayıncı başına takip takvimi, APScheduler işleri, canlı durum olayları (WebSocket), "Yayın Takvimi" sayfası | 1 |
| 3 | ~~Video kayıt sistemi~~ ✅ | `StreamRecorder` uygulaması (FFmpeg), izin kapısı zorunlu, disk kotası/temizlik, kayıt durumu takibi, "Kayıtlar" sayfası | 2, FFmpeg |
| 4 | **Qwen entegrasyonu** | Ollama üzerinden prompt şablonları, model yönetimi (`ai_models` tablosu), "AI Model Ayarları" sayfası | Ollama |
| 5 | **Whisper entegrasyonu** | Ses çıkarma + faster-whisper transkripsiyon, zaman damgalı segmentler, arka plan iş kuyruğu | 3, requirements-ai |
| 6 | **Önemli an tespit algoritması** | Transkript (Qwen ile anlamsal skor) + ses enerjisi + sohbet yoğunluğu sinyallerinin birleşimi, `ai_score` | 4, 5 |
| 7 | **Otomatik video kesme** | Skorlu aralıklardan kesit üretimi, min/max süre kuralları, "AI Kesitleri" sayfası (onay/ret) | 6 |
| 8 | **Video düzenleme** | Dikey format (9:16), altyazı yakma, küçük resim üretimi (OpenCV), intro/outro | 7 |
| 9 | **YouTube API entegrasyonu** | OAuth 2.0 akışı, güvenli token saklama, yükleme, kota takibi | — |
| 10 | **Otomatik yayınlama** | Planlı yükleme takvimi, başlık/açıklama/etiket üretimi (Qwen), "YouTube Yönetimi" sayfası | 8, 9 |
| 11 | **Performans analizi** | YouTube Analytics verileri, kesit başarısı ↔ AI skoru karşılaştırması, panelde grafikler | 10 |

## Teknik borç / altyapı notları

- Uzun süren işler (transkripsiyon, render) için kalıcı iş kuyruğu (SQLite tabanlı tablo + worker).
- Uç nokta sayısı artınca frontend'de TanStack Query'ye geçiş.
- Kimlik doğrulama (panel tek kullanıcılı olsa da yerel ağa açılmadan önce gerekli).
- Docker compose kurulumunun doğrulanması.
