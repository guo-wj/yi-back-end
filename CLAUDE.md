# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

易鉴 (Yi) — FastAPI backend for an AI 玄学 (Chinese metaphysics/divination) platform. Each feature (灵签/六爻/梅花/紫微/八字/老黄历/掌纹/面相) computes a deterministic result from traditional rules, then asks an LLM to write the interpretation. Code comments are in Chinese; match that when editing.

## Commands

This project uses `uv` (see `uv.lock`).

```bash
uv sync                         # install deps into .venv
uv run python app.py            # run dev server (uvicorn on 0.0.0.0:8000, hot-reload on *.py and .env)
uv run uvicorn app:app --reload # equivalent
```

API docs at `http://localhost:8000/docs`, health check at `/health`. There is no test suite or linter configured.

Requires `.env` (copy `.env.example`). A running **Redis** (`REDIS_URL`) and **SMTP** account are needed for the email-code login flow; LLM features need `DEEPSEEK_API_KEY` (text) and `ZHIPU_API_KEY` (vision).

## Architecture

Three layers; a request flows **router → service → AI client**.

- **`routers/`** — one module per feature, mounted under `/api/<feature>` in `routers/__init__.py`. Routers own Pydantic request/response models, call a service to compute the divination result, format it into a prompt via `services/prompts.py`, and await an AI client. Keep them thin.
- **`services/`** — business logic. `*_data.py` / `*_extractor.py` / `almanac.py` / `lunar.py` hold the deterministic traditional-计算 logic (gua casting, bazi, lunar calendar, etc.). `prompts.py` centralizes every system/user prompt template.
- **AI clients** — `deepseek_client.chat_completion` (text) and `vision_client.vision_completion[_multi]` (image). Both wrap OpenAI-compatible Async clients built by `services/openai_factory.make_async_openai_client`, which uses a shared `httpx.AsyncClient(trust_env=False)` to **bypass any system proxy** (do not remove `trust_env=False`).

### Cross-cutting conventions

- **Error handling**: AI clients catch OpenAI exceptions and re-raise via `services/ai_errors.map_ai_error`; missing API keys raise via `raise_service_not_configured`. `app.py` registers global exception handlers that turn `ValueError` into HTTP 400 and AI errors into 429/502 with friendly Chinese `detail`. **Raise `ValueError` for user-facing validation errors** rather than building responses in routers.
- **Blocking I/O in async**: SQLite (`auth_db`) and SMTP (`email_service`) are sync; always call them through `asyncio.to_thread(...)` from async code (see `auth_service.py`).
- **Config**: all settings come from `config.settings` (a plain `Settings` object reading env vars). `load_dotenv(override=True)` is required so uvicorn's reload subprocess picks up edited `.env` values.
- **Auth**: `services/auth_service` supports email-verification-code login (codes stored in Redis with TTL + resend cooldown) and phone/email + password. Users live in SQLite (`auth_db`); sessions are stateless JWTs. Protected endpoints read `Authorization: Bearer <token>` and resolve the user via `user_from_token`.
- **Vision pipeline** (palm/face): images are normalized/resized in `services/image_utils`, then Zhipu vision either returns features+interpretation in one call or extracts features for DeepSeek to interpret, toggled by `VISION_SINGLE_STAGE`.

### Adding a feature

Create `routers/<feature>.py` with an `APIRouter()`, register it in `routers/__init__.py`, put deterministic computation in `services/<feature>_data.py`, and add prompt builders to `services/prompts.py`.
