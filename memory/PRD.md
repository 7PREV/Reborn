# RIVALS — Arabic Esports Platform (Call of Duty)

## Problem Statement
Full-stack Arabic COD esports platform: email auth, clans with leaders/vices/players, join requests, invites, leader controls, private match chat (visible only to staff + both clans), BO3 map voting, dispute resolution, 24h chat history, search, leaderboards, knockout tournaments, scoring (+3 / -1 / -3), homepage banner carousel, **multi-league hub with decoupled per-league standings**, AI Referee, Personal/Clan Plus tiers, Public Blacklist.

## Stack
- Backend: FastAPI + Motor (async MongoDB), JWT HttpOnly cookies + Bearer fallback
- Frontend: React 19 + Tailwind + shadcn + lucide-react + sonner (RTL Arabic)
- AI: emergentintegrations + Emergent Universal Key (GPT text only — toxicity + welcome)
- Storage: disk for videos, base64 for images/banners/avatars; ObjectId always excluded
- Bg tasks: hourly chat/video cleanup + hourly league rotation

## Scoring (BO3) — applies to ALL standings (global + per-league)
- Map win threshold: 2-of-3
- Winner: +3 pts, +1 W
- Loser: -1 pt, +1 L
- Withdrawal: winning clan +3/+1W, withdrawing clan -3/+1L

## Feature Set (current)
### Core
- JWT cookie auth, role hierarchy (owner/admin/leader/vice/player)
- Clans CRUD + caps (7/12 with Plus) + 1/2 vices
- Match BO3 voting, dispute, withdraw
- 24h chat cleanup + image/video uploads (500MB Plus / 80MB Free)
- Global leaderboards (clans + players, with K/D)
- Tournaments single-elim + champion trophy + losers_bracket
- Hero banner ad carousel (owner-managed)

### Match flow & cooldowns
- Activision ID required, 2h clan-leave cooldown, 14d ACT change cooldown
- Clan challenge accept/reject workflow
- 10-min Grace + 10-min Prayer Break per map + auto-claim
- 30-min user prayer-break cooldown
- 3h pair cooldown (staff override)
- 6-member roster gate on challenge create/accept
- Clan archive + restore + transfer ownership
- Admin video reject with inline note

### Premium (Personal Plus / Clan Plus)
- Premium profile layout (banner + avatar overlap + accent_color + social rows)
- 3-day trial on register, dedicated `/plus` page (12.99 / 26.99 SAR)
- Clan Plus animated glow on leaderboard

### Communication & Moderation
- Public Blacklist with proof image
- Footer with Discord/Instagram/TikTok/Support
- Discord webhook (env `DISCORD_WEBHOOK_URL`) — tournament + match-start embeds
- Streaming: Twitch (real API), Kick (public), TikTok (link)
- AI Referee welcome bot (bilingual, posts league rules text + image on match start)
- Async toxicity scan on every chat msg + admin log at `/api/admin/toxicity-log`

### Multi-League Hub (Feb 2026 — finalized)
- `POST /api/leagues/custom` (admin) — name, game, rules text, rules image (data URL or http)
- `PUT  /api/leagues/{id}` — edit league
- `GET  /api/leagues/active` — public list
- `POST /api/leagues/{id}/join` — leader/vice register clan
- `POST /api/leagues/{id}/finish` — close league + award badge based on per-league standings
- **`GET  /api/leagues/{id}/leaderboard`** — decoupled per-league standings (each league independent)
- Per-league standings live in `db.league_standings` keyed by `{league_id, clan_id}`; updated on every match-finalize and withdrawal that has a `league_id`
- Public `/leagues` page lists active leagues with rules toggle + per-league leaderboard
- AI Referee posts the league name, rules text, and rules image into match chat on creation

### Other
- Monthly auto-league `دوري رايفلز - <month>` rotation + Trophy Room
- Hero banner ad carousel + admin CMS for Rules + Banners + Leagues

## Removed Features (Feb 2026)
- **Scoreboard Vision OCR** — `POST /api/matches/{id}/scoreboard` endpoint and the "رفع لوحة النتائج" chat-room button have been removed entirely. K/D is no longer auto-parsed from screenshots (saving AI credits + simpler UX).

## API surface (key endpoints)
- POST /api/leagues/custom            (staff)
- PUT  /api/leagues/{id}              (staff)
- GET  /api/leagues/active            (public)
- GET  /api/leagues/{id}/leaderboard  (public) — NEW
- POST /api/leagues/{id}/join         (leader/vice)
- POST /api/leagues/{id}/finish       (staff → awards badge)
- GET  /api/admin/toxicity-log        (staff)
- POST /api/admin/users/{id}/personal-plus  (owner)
- POST /api/admin/clans/{id}/plus     (owner)
- GET  /api/matches/{id}/h2h          (public)
- POST /api/matches/{id}/match-prayer-break + /match-prayer-resume

## Test Coverage
- /app/backend/tests/test_rivals.py + test_rivals_launch.py + test_league_standings.py
- 68/68 passing (Feb 2026 iteration 4)

## Pending external creds (gracefully handled when missing)
- TWITCH_CLIENT_ID + TWITCH_CLIENT_SECRET → real Twitch live detection
- DISCORD_WEBHOOK_URL → community embeds
- Resend/SendGrid API key → real password-reset emails
- MongoDB Atlas creds (last attempt returned bad auth — staying on local Mongo until user supplies working creds)
