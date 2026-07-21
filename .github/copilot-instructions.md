# Copilot instructions for RIVALS

## Big picture architecture
- Monorepo with two deployable apps: FastAPI backend in [backend/server.py](backend/server.py) and React frontend in [frontend/src](frontend/src).
- Backend is a single-file API surface (~6k lines) using `APIRouter(prefix="/api")`; most business rules live inline in endpoint handlers and helper functions.
- Data store is MongoDB via Motor (`AsyncIOMotorClient`); documents use app-level UUID `id` fields (not Mongo `_id`) and responses intentionally exclude `_id`.
- Discord integration is async/job-based: backend enqueues docs into `db.discord_jobs` (`_enqueue_discord_job`) and worker bot polls/processes them in [backend/discord_bot/bot.py](backend/discord_bot/bot.py).
- Auth model: HttpOnly cookie + Bearer fallback (`_extract_token_from_request`), refresh-session flow, and axios auto-refresh queue in [frontend/src/api.js](frontend/src/api.js).

## Critical workflows (local/dev)
- Backend run (from `backend/`): `uvicorn server:app --reload --port 8001` (tests default to `http://127.0.0.1:8001`).
- Discord bot run (from `backend/`): `python discord_bot/bot.py`.
- Frontend run (from `frontend/`): `npm start` (CRACO, port 3000).
- Core integration tests (backend): `pytest backend/tests/test_rivals.py backend/tests/test_rivals_launch.py backend/tests/test_league_standings.py`.
- Deployment shape is codified in [render.yaml](render.yaml): separate web service (`uvicorn`) and worker (`python discord_bot/bot.py`).

## Project-specific patterns to preserve
- Keep Arabic-first UX/messages for user-facing strings (see pages/components in [frontend/src/pages](frontend/src/pages)); UI is RTL by default (`dir="rtl"` in [frontend/public/index.html](frontend/public/index.html)).
- Keep canonical game assumptions unless explicitly changed: `GAMES = ["Call of Duty"]`, BO3 constants in [backend/server.py](backend/server.py).
- Reuse existing helper guards (`is_staff`, `is_owner`, `_enforce_ban_guard`, `_rate_limit_or_429`) instead of adding parallel authorization/rate-limit logic.
- For new Mongo models, follow existing indexing-at-startup pattern in `startup()` and store ISO timestamps via `iso(now_utc())`.
- For API additions consumed by frontend, add wrappers in [frontend/src/api.js](frontend/src/api.js) and keep `withCredentials: true` behavior.

## Integration points and env contracts
- Required core env: `MONGO_URI`/`MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `CORS_ORIGINS` (mandatory in production).
- Seeded admin/owner accounts come from env in backend startup (`ADMIN_EMAIL/PASSWORD`, `OWNER_EMAIL/PASSWORD`).
- Discord bridge/security: optional `DISCORD_BRIDGE_SECRET`; bot/helper calls use `x-discord-bridge-secret` when configured.
- Bot depends on Discord IDs/role IDs (`DISCORD_GUILD_ID`, `DISCORD_BOT_TOKEN`, support/ticket/plus/rank IDs) and dynamic ticket categories from `discord_ticket_categories`.
- Frontend API base uses `REACT_APP_BACKEND_URL` and appends `/api` in [frontend/src/api.js](frontend/src/api.js).

## Known product decisions (do not regress)
- Scoreboard OCR endpoint is intentionally removed (tests assert `/api/matches/{id}/scoreboard` returns 404/405).
- League standings are per-league (collection `league_standings` keyed by `{league_id, clan_id}`), not global-only.
- Match chat/media retention is intentional: hourly cleanup loop removes messages older than 24h and deletes stored video files.
- Discord notifications favor start/transfer events; score-post notifications are intentionally disabled in bot job handling.
