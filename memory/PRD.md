# RIVALS — Arabic Esports Platform (Call of Duty)

## Problem Statement
Build a full-stack Arabic COD esports platform: email auth, clans with leaders/vices/players, join requests, invites, leader controls, private match chat (visible only to staff + both clans), BO3 map voting, dispute resolution, 24h history, search, leaderboards, knockout tournaments, point system (+3 / -1 / -3), homepage banner carousel.

## Stack
- Backend: FastAPI + Motor (async MongoDB), JWT HttpOnly cookies + Bearer fallback
- Frontend: React 19 + Tailwind + shadcn + lucide-react + sonner (RTL Arabic)
- AI: emergentintegrations + Emergent Universal Key (GPT-5.4 text + vision)
- Storage: disk for videos, base64 for images/banners/avatars; ObjectId always excluded
- Bg tasks: hourly chat/video cleanup + hourly league rotation

## Implemented Feature Set (May 2026 → Feb 2026)
### Core
- JWT cookie auth, role hierarchy (owner/admin/leader/vice/player)
- Clans CRUD + caps (7/12 with Plus) + 1/2 vices
- Match BO3 voting, dispute, withdraw (+3/-1/-3 points)
- 24h chat cleanup + image/video uploads (500MB Plus / 80MB Free)
- Leaderboards (clans + players, with K/D)
- Tournaments single-elim + champion trophy
- Hero banner ad carousel (owner-managed)

### Launch Batch v1
- Activision ID required, 2h clan-leave cooldown, 14d ACT change cooldown
- Clan challenge accept/reject workflow
- 10-min Grace Period + 10-min Prayer Break per map + auto-claim
- Admin video reject with inline note
- 3h pair cooldown (staff override)
- Clan archive (kick all + 2h cooldown) + restore + transfer ownership
- Admin edit user/clan, MOCKED forgot-password
- Public Blacklist page with proof image
- Monthly auto-league `دوري رايفلز - <month>` rotation + Trophy Room
- Streaming: Twitch (real API), Kick (public), TikTok (link)
- Tournament losers_bracket flag

### Launch Batch v2
- Premium profile layout (banner + avatar overlap + big ACT typography + social rows)
- Personal Plus tier with 3-day trial on register
- Avatar/banner/accent_color upload gated behind Personal Plus
- Dedicated `/plus` page with 2 cards (Personal 12.99 SAR / Clan 26.99 SAR)
- Footer with Discord/Instagram/TikTok/Support links
- Discord webhook (env `DISCORD_WEBHOOK_URL`) — new tournament + match-start embeds
- Career stats W/L + K/D ratio (2 decimals) on users and clans
- 6-member roster gate on challenge create/accept
- Act required to join clan
- 30-min user prayer-break cooldown
- Head-to-Head widget in match room
- Public PlayerProfilePage with same premium layout
- Players link from anywhere → `/players/:id`
- Clan Plus animated glow on leaderboard (`row.is_clan_plus`)
- Registration terms checkbox + `accepted_terms` validation

### Final Batch (Feb 2026)
- **Multi-league system**: `POST /api/leagues/custom`, `GET /api/leagues/active`, `POST /api/leagues/{id}/join`, `POST /api/leagues/{id}/finish` — multiple custom leagues run in parallel with own name/game/rules; clans pick which to queue
- **League champion badges**: shown next to clan name on leaderboard
- **AI Referee Bot** (welcomes both clans on match start; bilingual)
- **Toxicity log**: every chat msg async-scanned; warnings posted + stored in `db.toxicity_log`; admin view at `/api/admin/toxicity-log`
- **AI Vision Scoreboard OCR**: `POST /api/matches/{id}/scoreboard` reads endgame screenshot, updates each player's lifetime K/D stats
- Mongo URL fallback to `mongodb://localhost:27017` for dev safety

## API surface (key new endpoints)
- POST /api/leagues/custom            (staff)
- GET  /api/leagues/active            (public)
- POST /api/leagues/{id}/join         (leader/vice)
- POST /api/leagues/{id}/finish       (staff → awards badge)
- POST /api/matches/{id}/scoreboard   (vision OCR → updates K/D)
- GET  /api/admin/toxicity-log        (staff)
- POST /api/admin/users/{id}/personal-plus  (owner only)
- POST /api/admin/clans/{id}/plus     (owner only)
- GET  /api/matches/{id}/h2h          (public)
- POST /api/matches/{id}/match-prayer-break + /match-prayer-resume
- POST /api/clans/{id}/restore, /archive, /admin/clans/{id}/transfer/{m}

## Pending external creds (gracefully handled when missing)
- TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET → real Twitch live detection
- DISCORD_WEBHOOK_URL → community embeds
- Resend/SendGrid API key → real password-reset emails
- MongoDB Atlas user credentials (the supplied one returned bad auth — currently on local Mongo)
