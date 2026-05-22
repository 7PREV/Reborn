# RIVALS — Arabic Esports Platform (Call of Duty)

## Problem Statement (Original)
بناء موقع رياضات إلكترونية: تسجيل بريد، كلانات بقادة ونواب ولاعبين، طلبات انضمام ودعوات، تحكم القائد، شات خاص أثناء المباراة (مرئي للمنظمين والكلانَين فقط، يكتب فيه القائد ونائبه والإدارة فقط)، لوحة نتائج، مباريات حية، تاريخ 24 ساعة، بحث كلان وبحث لاعب.

## User Choices
- Auth: Email/password + JWT HttpOnly cookies
- Chat: Text + Image + Video (24h auto-cleanup)
- Game: Call of Duty only (BO3)
- Theme: Modern dark with gold accents, RTL Arabic
- Stream: Twitch (real-time API), Kick (best-effort public), TikTok (link only)
- Email: Forgot-password MOCKED (admin dashboard shows pending tokens — waiting on Resend/SendGrid key)

## Implemented (May 2026 — latest)
### Core
- JWT HttpOnly cookie auth + Bearer fallback
- Clans CRUD, roles (leader/vice/player), kick/promote/leave
- Membership caps (7 default / 12 Plus), vice caps (1 / 2 Plus)
- Plus toggle (free during preview) + 7-day Plus reward when clan fills
- Join requests + invites flow
- Matches BO3 with map voting + admin dispute resolve
- Withdraw mechanism (-3 / +3)
- Chat with text/image/video uploads (500MB Plus / 100MB Free) — disk storage
- 24h auto-cleanup background task for chat + video files
- Leaderboards (clans + players), live + 24h history
- Player/clan search, Rules CRUD
- Tournaments (single-elim, byes, BO3 matches per round, champion trophy)
- Hero banner ad carousel (Owner-managed)
- Owner role (Prev) + admin role hierarchy

### Latest launch batch (May 22, 2026)
- **Activision ID (`act`) required at registration** + editable from profile
- **2h clan-leave cooldown** (leave/kick/archive)
- **Clan challenge → request/accept/reject flow** (no auto-match)
- **Match map timers**: 10-min Grace Period + 10-min Prayer Break + auto-claim win
- **Admin video reject NOTE attached inline** below X icon
- **3-hour pair cooldown** between same two clans (staff can override)
- **Clan archive (Power button)** kicks all members + applies 2h cooldown
- **Owner/Admin edit** username/email/password/act for users
- **Owner/Admin edit** clan name/tag/description
- **Forgot password** (MOCKED) — generates token; admin sees pending list with `token` field
- **Blacklist page** (`/blacklist`, staff only) with player account snapshot + cheat tool + proof image upload
- **Monthly League auto-rotation** — `دوري رايفلز - <month-ar>` resets points each new month + grants trophy to top clan
- **Trophy Room** in ClanDetailPage (league + tournament trophies)
- **Live streaming integration**:
  - Profile fields: `twitch_url`, `kick_url`, `tiktok_url`
  - `/api/users/{id}/live` + `/api/matches/{id}/live-streams`
  - Twitch: real-time via Helix API (needs `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` env)
  - Kick: public unofficial endpoint (best-effort)
  - TikTok: link-only (no live detection)
  - Match page right sidebar shows live thumbnails with click-through
- **Tournament `losers_bracket` flag** (UI checkbox; double-elim logic still single-elim under the hood — flag stored for future expansion)
- **Brand rename**: All "Arena" references → "Rivals"

## Architecture
- Backend: FastAPI + Motor (MongoDB)
- Frontend: React 19 + Tailwind + shadcn + lucide-react + sonner
- Storage: UUID string ids, ISO timestamps, exclude _id from responses, disk for videos
- Auth: JWT in HttpOnly cookie + Authorization Bearer fallback
- Background: hourly chat cleanup loop + hourly league rotation loop

## Pending / Backlog
- **P0**: Provide Twitch Client-ID + Secret to enable real Twitch live detection
- **P1**: Resend/SendGrid API key to send actual password-reset emails (currently MOCKED)
- **P2**: Implement true double-elimination bracket logic when losers_bracket flag is true
- **P2**: Real WebSocket chat (current is polling)
- **P2**: Google OAuth (placeholder toast)
- **P2**: Paid Plus subscription (Stripe)
- **P2**: Server-side pagination on clans/players lists
- **P3**: Real object-storage (S3) for media instead of disk
- **P3**: Notifications (in-app + email) for invites/match start

## Testing
- 29/29 pytest tests passing in `/app/backend/tests/test_rivals.py`
- Frontend smoke-test: homepage renders with hero carousel + clan rankings
