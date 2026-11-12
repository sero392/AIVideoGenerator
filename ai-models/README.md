# ai-models/

Yerel model dosyaları için ayrılmış klasör. İçeriği Git'e dahil edilmez (yalnızca bu README).

| Model | Nerede saklanır | Nasıl kurulur |
|---|---|---|
| Qwen (LLM) | Ollama kendi dizininde tutar (`~/.ollama/models`) | `ollama pull qwen2.5:7b` |
| faster-whisper | İlk kullanımda Hugging Face önbelleğine iner; istenirse buraya indirilebilir | `pip install -r backend/requirements-ai.txt` |

Model seçimi merkezi olarak yapılır:

- Bağlantı ve varsayılan model: `backend/.env` (`OLLAMA_BASE_URL`, `OLLAMA_DEFAULT_MODEL`, `WHISPER_*`)
- Ayar detayları: `config/settings.json` → `ai`

Çalışma zamanında ücretli bir API'ye (Claude dahil) bağımlılık yoktur; sistem yerel modellerle çalışacak şekilde tasarlanmıştır.
