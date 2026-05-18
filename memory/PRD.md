# RIVALS — Arabic Esports Platform (Call of Duty)

## Problem Statement (Original)
بناء موقع رياضات إلكترونية: تسجيل بريد، كلانات بقادة ونواب ولاعبين، طلبات انضمام ودعوات، تحكم القائد، شات خاص أثناء المباراة (مرئي للمنظمين والكلانَين فقط، يكتب فيه القائد ونائبه والإدارة فقط)، لوحة نتائج، مباريات حية، تاريخ 24 ساعة، بحث كلان وبحث لاعب.

## User Choices
- Auth: Email/password (Google placeholder)
- Chat: Text + Image + Video
- Game: Call of Duty only
- Admin: Pre-seeded (admin@rivals.gg / Admin@12345)
- Theme: Modern elegant dark with gold accents, RTL Arabic

## Implemented (May 2026)
- JWT auth (bcrypt + httpOnly cookie + Bearer header)
- Clans: create, search, roster, leader/vice/player roles, kick/promote/leave/delete
- Membership: 7 default / 12 Plus, vice cap 1 / 2 Plus
- Plus toggle (free during preview)
- Join requests + Invites with full flow
- Matches: BO3 maps voting per map by each leader; agreement→winner set; disagreement→disputed; admin resolves; auto-finish at 2 map wins; +25/-10 points
- Dispute button by leaders
- Chat: text+image+video uploads (base64), polling every 4s
- Outsider clans see only media; playing clans + admin see full
- Image opponent decision (✓/✗); Video admin decision (✓/✗/note)
- Rules CRUD (admin-only management; public read)
- Leaderboards (clans + players)
- Live matches + 24h history
- Player/clan search
- Admin dashboard with dispute alerts

## Architecture
- Backend: FastAPI + Motor (MongoDB)
- Frontend: React 19 + Tailwind + shadcn + lucide-react + sonner toasts
- Data: UUID string ids, ISO timestamps, exclude _id from responses
- Auth: JWT in httpOnly cookie + Authorization Bearer fallback

## Deferred / Backlog
- P1: Real WebSocket for chat (current is polling)
- P1: Google OAuth (currently placeholder toast)
- P2: Payment integration for Plus subscription (currently free toggle)
- P2: Server-side pagination on clans/players lists
- P2: Real object-storage for media (currently base64 inline)
- P2: Notifications (in-app + email) for invites/match start
