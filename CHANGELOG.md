# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versiyalash: [SemVer](https://semver.org/).

## [1.1.0] - 2026-11-02
### Security
- AI so'rovlari backend orqali: `POST /ai/chat`, `POST /ai/analyze`. Frontend LLM kalitini bilmaydi.
- LLM sozlamalari env'dan (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT`), OpenAI-mos har qanday API ishlaydi.
- Xatolar: 503 (sozlanmagan), 504 (timeout), 502 (LLM xatosi). Tibbiy disclaimer saqlandi.

## [1.0.0] - 2026-11-02
### Added
- Dastlabki import: FastAPI backend, Vue 3 frontend, Docker Compose.

### Security
- Frontend kodidan Groq API kaliti olib tashlandi; AI so'rovlari vaqtincha o'chirilgan.
