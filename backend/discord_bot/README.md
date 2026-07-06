# RIVALS Discord Bot (discord.py)

## Run
- Install dependencies from [backend/requirements.txt](../requirements.txt)
- Set env vars:
  - `DISCORD_BOT_TOKEN`
  - `DISCORD_GUILD_ID`
  - `MONGO_URI` (or `MONGO_URL`)
  - `DB_NAME`
  - optional: `DISCORD_WELCOME_CHANNEL_ID`, `DISCORD_SUPPORT_ROLE_ID`, `DISCORD_TICKET_CATEGORY_ID`, `DISCORD_LEVEL_ROLE_MAP`
  - optional: `DISCORD_TICKET_PANEL_BANNER_GIF_URL`

Then run:

`python backend/discord_bot/bot.py`

## Architecture (credit/rate-limit friendly)
- Website/API enqueues one-shot jobs into `discord_jobs`.
- Bot polls queued jobs with retry/backoff and processes only deltas (no loops).
- Clan role sync is event-driven (`clan_role_sync_member`) and only runs on join/leave change.
- Plus channels are created on-demand by explicit API trigger.

## Ticket System (Dynamic + Persistent)
- Ticket categories are read from backend collection `discord_ticket_categories`.
- Panel uses a persistent dropdown (`discord.ui.Select`) and keeps working after bot restarts.
- Publish panel with:
  - Prefix command: `!ticketpanel`
  - Slash command: `/tickets_panel`
- Created tickets are private channels with strict overwrites:
  - `@everyone`: no view
  - ticket creator: view/send
  - category support role: view/send/manage
- Each ticket gets action buttons:
  - `Close` (marks closed + deletes channel)
  - `Archive / Lock` (locks creator writing + archives state)
