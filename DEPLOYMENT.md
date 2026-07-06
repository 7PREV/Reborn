# Deployment (Vercel + Render)

## 1) Deploy backend + bot on Render

1. Push this repository to GitHub.
2. In Render, create a **Blueprint** from repo root using [render.yaml](render.yaml).
3. Render will create:
   - `rivals-backend` (web service)
   - `rivals-discord-bot` (worker)
4. Set required env vars in Render dashboard:
   - Common: `MONGO_URI`, `DB_NAME=rivals`
   - Backend: `CORS_ORIGINS` (your Vercel URL)
   - Bot: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID` and role/channel IDs

Backend health URL after deploy:
- `https://<backend-service>.onrender.com/api/health`

## 2) Deploy frontend on Vercel

1. Import repo in Vercel and set project root to `frontend`.
2. Vercel will use [frontend/vercel.json](frontend/vercel.json).
3. Set env var:
   - `REACT_APP_BACKEND_URL=https://<backend-service>.onrender.com`
4. Redeploy frontend after env is set.

## 3) Final CORS wiring

Set backend Render env:
- `CORS_ORIGINS=https://<your-vercel-domain>`

Then redeploy backend once.

## 4) Quick verification

- Frontend loads without API CORS errors.
- `GET /api/health` returns `ok: true`.
- Discord bot logs show successful login and command sync.
