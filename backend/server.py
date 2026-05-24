from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

# ---------------- Setup ----------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"
ACCESS_MIN = 60 * 24

GAMES = ["Call of Duty"]
MAPS_TO_WIN = 2  # Best of 3
BO_TOTAL = 3

CLAN_LIMIT_DEFAULT = 7
CLAN_LIMIT_PLUS = 12
VICE_LIMIT_DEFAULT = 1
VICE_LIMIT_PLUS = 2

ACT_CHANGE_COOLDOWN_DAYS = 14
ONLINE_WINDOW_MINUTES = 5
MATCH_PRAYER_BREAK_SECONDS = 15 * 60

CLAN_PLUS_REWARD_THRESHOLD = 6       # Founders Plus unlock once clan reaches exactly 6 members
CHALLENGE_MIN_MEMBERS = 6            # Clan must have ≥6 members to challenge / accept
PERSONAL_PLUS_TRIAL_DAYS = 3         # Free trial granted at registration
PRAYER_BREAK_USER_COOLDOWN_MIN = 30  # 30 min anti-spam cooldown on prayer-break button

app = FastAPI(title="Rivals Esports API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rivals")


# ---------------- Helpers ----------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def make_token(user_id: str, email: str, role: str) -> str:
    return jwt.encode({
        "sub": user_id, "email": email, "role": role,
        "exp": now_utc() + timedelta(minutes=ACCESS_MIN),
    }, JWT_SECRET, algorithm=JWT_ALG)


def is_staff(user: dict) -> bool:
    """Owner or admin both count as staff for moderation tasks."""
    return user.get("role") in ("owner", "admin")


def is_owner(user: dict) -> bool:
    return user.get("role") == "owner"


def user_is_plus(u: dict) -> bool:
    """Effective Plus: manual flag OR temporary expiry not yet passed."""
    if u.get("is_plus"):
        return True
    exp = u.get("plus_expires_at")
    if not exp:
        return False
    try:
        return datetime.fromisoformat(exp) > now_utc()
    except Exception:
        return False


def user_is_personal_plus(u: dict) -> bool:
    """Personal Plus is a per-user subscription tier (separate from clan Plus).
    Free trial = 3 days from registration. Active if `personal_plus_until` > now."""
    iso_until = u.get("personal_plus_until")
    if not iso_until:
        return False
    try:
        return datetime.fromisoformat(iso_until) > now_utc()
    except Exception:
        return False


def compute_kd(wins: int, losses: int) -> float:
    """Win/Loss ratio formatted as K/D — losses=0 returns float wins."""
    if losses <= 0:
        return float(wins)
    return round(wins / losses, 2)


def sanitize_user(u: dict) -> dict:
    last_seen = u.get("last_seen_at")
    is_online = False
    if last_seen:
        try:
            is_online = (now_utc() - datetime.fromisoformat(last_seen)).total_seconds() < ONLINE_WINDOW_MINUTES * 60
        except Exception:
            is_online = False
    wins = u.get("wins", 0)
    losses = u.get("losses", 0)
    return {
        "id": u["id"],
        "email": u["email"],
        "username": u["username"],
        "act": u.get("act", ""),
        "act_changed_at": u.get("act_changed_at"),
        "role": u.get("role", "player"),
        "clan_id": u.get("clan_id"),
        "points": u.get("points", 0),
        "wins": wins,
        "losses": losses,
        "kd": compute_kd(wins, losses),
        "avatar": u.get("avatar"),
        "banner": u.get("banner"),
        "accent_color": u.get("accent_color"),
        "is_plus": user_is_plus(u),
        "is_personal_plus": user_is_personal_plus(u),
        "personal_plus_until": u.get("personal_plus_until"),
        "plus_expires_at": u.get("plus_expires_at"),
        "clan_cooldown_until": u.get("clan_cooldown_until"),
        "twitch_url": u.get("twitch_url", ""),
        "kick_url": u.get("kick_url", ""),
        "tiktok_url": u.get("tiktok_url", ""),
        "last_seen_at": last_seen,
        "is_online": is_online,
        "prayer_break_cooldown_until": u.get("prayer_break_cooldown_until"),
        "created_at": u.get("created_at"),
    }


def _assert_act_set(user: dict) -> None:
    """Block clan join attempts when player's Activision ID is missing."""
    if not (user.get("act") or "").strip():
        raise HTTPException(400, "يجب حفظ Activision ID في الملف الشخصي قبل الانضمام لكلان")


def _assert_clan_can_match(clan: dict) -> None:
    """Roster minimum gate for issuing/accepting matches."""
    if clan.get("archived"):
        raise HTTPException(400, "هذا الكلان مؤرشف")
    members = len(clan.get("member_ids", []))
    if members < CHALLENGE_MIN_MEMBERS:
        raise HTTPException(400, f"الكلان يحتاج {CHALLENGE_MIN_MEMBERS} لاعبين على الأقل لخوض المباريات ({members}/{CHALLENGE_MIN_MEMBERS})")


CLAN_LEAVE_COOLDOWN_HOURS = 2


def _cooldown_remaining_seconds(user: dict) -> int:
    """Returns seconds remaining on the user's clan-join cooldown, 0 if none."""
    iso_until = user.get("clan_cooldown_until")
    if not iso_until:
        return 0
    try:
        dt = datetime.fromisoformat(iso_until)
    except Exception:
        return 0
    delta = (dt - now_utc()).total_seconds()
    return max(0, int(delta))


def _assert_no_cooldown(user: dict) -> None:
    remaining = _cooldown_remaining_seconds(user)
    if remaining > 0:
        mins = (remaining + 59) // 60
        raise HTTPException(400, f"لا يمكنك الانضمام لكلان الآن. المتبقي {mins} دقيقة")


async def _start_clan_leave_cooldown(user_id: str) -> None:
    until = iso(now_utc() + timedelta(hours=CLAN_LEAVE_COOLDOWN_HOURS))
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"clan_id": None, "clan_cooldown_until": until}},
    )


async def _maybe_grant_full_clan_reward(clan_id: str) -> bool:
    """When a clan first reaches exactly CLAN_PLUS_REWARD_THRESHOLD (6) active members,
    grant the leader 7-day Plus. Returns True if reward was just granted.
    The check is idempotent — `founder_reward_given` prevents re-issue."""
    clan = await db.clans.find_one({"id": clan_id})
    if not clan:
        return False
    if clan.get("founder_reward_given"):
        return False
    if clan.get("archived"):
        return False
    members = clan.get("member_ids", [])
    if len(members) < CLAN_PLUS_REWARD_THRESHOLD:
        return False
    leader = await db.users.find_one({"id": clan["leader_id"]})
    if not leader:
        return False
    # Only grant if leader is not already on permanent Plus
    if not leader.get("is_plus"):
        new_expiry = now_utc() + timedelta(days=7)
        existing_exp = leader.get("plus_expires_at")
        if existing_exp:
            try:
                cur = datetime.fromisoformat(existing_exp)
                if cur > new_expiry:
                    new_expiry = cur + timedelta(days=7)
            except Exception:
                pass
        await db.users.update_one({"id": leader["id"]}, {"$set": {"plus_expires_at": iso(new_expiry)}})
    await db.clans.update_one({"id": clan_id}, {"$set": {"founder_reward_given": True}})
    return True


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "User not found")
    # Record presence (used for online-clan filtering)
    try:
        await db.users.update_one({"id": user["id"]}, {"$set": {"last_seen_at": iso(now_utc())}})
    except Exception:
        pass
    return user


def set_auth_cookie(resp: Response, token: str):
    resp.set_cookie(
        "access_token", token,
        httponly=True, secure=True, samesite="none",
        max_age=ACCESS_MIN * 60, path="/",
    )


# ---------------- Models ----------------
class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=30)
    password: str = Field(min_length=6, max_length=128)
    act: str = Field(min_length=2, max_length=40)  # In-game COD name


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ClanCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    tag: str = Field(min_length=2, max_length=8)
    description: Optional[str] = ""


class InviteIn(BaseModel):
    user_id: str


class HandleRequestIn(BaseModel):
    action: Literal["accept", "reject"]


class MatchCreateIn(BaseModel):
    clan_a_id: str
    clan_b_id: str
    notes: Optional[str] = ""


class ChallengeIn(BaseModel):
    opponent_clan_id: str
    notes: Optional[str] = ""


class ChatMessageIn(BaseModel):
    text: Optional[str] = ""
    image: Optional[str] = None  # base64 data URL
    video: Optional[str] = None  # base64 data URL


class MapVoteIn(BaseModel):
    map_index: int
    winner_clan_id: str


class AdminResolveMapIn(BaseModel):
    map_index: int
    winner_clan_id: str


class AdminMediaDecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: Optional[str] = ""


class OpponentImageDecisionIn(BaseModel):
    decision: Literal["accept", "reject"]


class RuleIn(BaseModel):
    title: str
    body: str
    order: int = 0


class ProfileUpdateIn(BaseModel):
    twitch_url: Optional[str] = ""
    kick_url: Optional[str] = ""
    tiktok_url: Optional[str] = ""
    act: Optional[str] = None
    avatar: Optional[str] = None        # base64 data URL (≤2MB) — Personal Plus only
    banner: Optional[str] = None        # base64 data URL (≤3MB) — Personal Plus only
    accent_color: Optional[str] = None  # hex string — Personal Plus only


class AdminUserEditIn(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    act: Optional[str] = None


class AdminClanEditIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=40)
    tag: Optional[str] = Field(default=None, min_length=2, max_length=8)
    description: Optional[str] = None


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class BlacklistIn(BaseModel):
    player_name: str = Field(min_length=2, max_length=80)
    player_user_id: Optional[str] = None
    player_email: Optional[str] = ""
    cheat_tool: str = Field(min_length=1, max_length=120)
    details: Optional[str] = ""
    proof_image: Optional[str] = ""  # base64 data URL or upload URL


# ---------------- Startup ----------------
async def _cleanup_old_chat_messages() -> int:
    """Delete chat messages older than 24h + their video files. Returns count deleted."""
    cutoff_iso = iso(now_utc() - timedelta(hours=24))
    cursor = db.chat_messages.find(
        {"created_at": {"$lt": cutoff_iso}}, {"_id": 0, "video": 1}
    )
    deleted_files = 0
    async for msg in cursor:
        v = msg.get("video")
        if v and isinstance(v, str) and v.startswith("/api/uploads/videos/"):
            fname = v.rsplit("/", 1)[-1]
            fpath = UPLOAD_DIR / fname
            if fpath.exists():
                fpath.unlink(missing_ok=True)
                deleted_files += 1
    result = await db.chat_messages.delete_many({"created_at": {"$lt": cutoff_iso}})
    if result.deleted_count or deleted_files:
        logger.info(f"Cleanup: removed {result.deleted_count} messages, {deleted_files} video files")
    return result.deleted_count


async def _periodic_cleanup_loop() -> None:
    """Background loop running every hour."""
    while True:
        try:
            await _cleanup_old_chat_messages()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Cleanup loop error: {exc}")
        await asyncio.sleep(3600)


@app.on_event("startup")
async def startup() -> None:
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username")
    await db.clans.create_index("name", unique=True)
    await db.clans.create_index("tag", unique=True)
    await db.matches.create_index("status")
    await db.chat_messages.create_index("match_id")
    await db.join_requests.create_index([("clan_id", 1), ("user_id", 1)])
    await db.rules.create_index("order")

    # Seed admin (regular admin)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@rivals.gg")
    admin_pw = os.environ.get("ADMIN_PASSWORD", "Admin@12345")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "username": "Admin",
            "password_hash": hash_pw(admin_pw),
            "role": "admin",
            "points": 0,
            "clan_id": None,
            "avatar": None,
            "is_plus": True,
            "created_at": iso(now_utc()),
        })
        logger.info(f"Seeded admin: {admin_email}")
    elif not verify_pw(admin_pw, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_pw(admin_pw), "role": "admin"}}
        )

    # Seed Owner (single super-admin who manages admins)
    owner_email = os.environ.get("OWNER_EMAIL", "prev@rivals.gg")
    owner_username = os.environ.get("OWNER_USERNAME", "Prev")
    owner_pw = os.environ.get("OWNER_PASSWORD", "Prev@Rivals2026")
    existing_owner = await db.users.find_one({"email": owner_email})
    if not existing_owner:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": owner_email,
            "username": owner_username,
            "password_hash": hash_pw(owner_pw),
            "role": "owner",
            "points": 0,
            "clan_id": None,
            "avatar": None,
            "is_plus": True,
            "created_at": iso(now_utc()),
        })
        logger.info(f"Seeded owner: {owner_email}")
    elif existing_owner.get("role") != "owner":
        await db.users.update_one({"email": owner_email}, {"$set": {"role": "owner"}})

    # Seed default rules
    if await db.rules.count_documents({}) == 0:
        defaults = [
            {"title": "احترام اللاعبين", "body": "ممنوع السب أو التحرش بأي شكل. أي إساءة تؤدي للحظر الفوري.", "order": 1},
            {"title": "الغش ممنوع", "body": "أي استخدام لبرامج خارجية أو هاكات يؤدي لحظر دائم وخصم نقاط الكلان.", "order": 2},
            {"title": "النتائج عبر اللقطات", "body": "يجب على القائد الفائز رفع لقطة الشاشة في الشات. الكلان الخصم يؤكد أو يرفض.", "order": 3},
            {"title": "نظام BO3", "body": "كل مباراة 3 خرائط. أول كلان يفوز بخريطتين يربح المباراة.", "order": 4},
            {"title": "النزاعات", "body": "عند الخلاف يقرر المنظم بعد مراجعة الأدلة في الشات.", "order": 5},
        ]
        for r in defaults:
            await db.rules.insert_one({"id": str(uuid.uuid4()), **r, "created_at": iso(now_utc())})

    cred_dir = Path("/app/memory")
    cred_dir.mkdir(parents=True, exist_ok=True)
    (cred_dir / "test_credentials.md").write_text(
        f"""# Test Credentials

## Admin (Organizer)
- Email: `{admin_email}`
- Password: `{admin_pw}`
- Role: admin

## Auth Endpoints
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/logout
- GET  /api/auth/me
"""
    )

    # Start background cleanup task (24h chat messages + video files)
    asyncio.create_task(_periodic_cleanup_loop())
    # Start monthly league rotation loop
    asyncio.create_task(_league_rotation_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    client.close()


# ---------------- AUTH ----------------
@api.post("/auth/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "البريد مسجل من قبل")
    if await db.users.find_one({"username": body.username}):
        raise HTTPException(400, "اسم المستخدم محجوز")
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "username": body.username,
        "act": body.act.strip(),
        "password_hash": hash_pw(body.password),
        "role": "player",
        "points": 0,
        "wins": 0,
        "losses": 0,
        "clan_id": None,
        "avatar": None,
        "banner": None,
        "accent_color": None,
        "is_plus": False,
        "personal_plus_until": iso(now_utc() + timedelta(days=PERSONAL_PLUS_TRIAL_DAYS)),
        "clan_cooldown_until": None,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(user)
    token = make_token(user["id"], user["email"], user["role"])
    set_auth_cookie(response, token)
    return {"user": sanitize_user(user), "token": token}


@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_pw(body.password, user["password_hash"]):
        raise HTTPException(401, "البريد أو كلمة المرور غير صحيحة")
    token = make_token(user["id"], user["email"], user["role"])
    set_auth_cookie(response, token)
    return {"user": sanitize_user(user), "token": token}


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return sanitize_user(user)


@api.post("/me/plus")
async def toggle_plus(user: dict = Depends(get_current_user)):
    """Toggle Plus subscription (free during preview)."""
    new_val = not user.get("is_plus", False)
    await db.users.update_one({"id": user["id"]}, {"$set": {"is_plus": new_val}})
    return {"is_plus": new_val}


# ---------------- USERS ----------------
@api.get("/users/search")
async def search_users(q: str = ""):
    query = {}
    if q:
        query = {"$or": [
            {"username": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]}
    docs = await db.users.find(query, {"_id": 0}).limit(50).to_list(50)
    return [sanitize_user(d) for d in docs]


@api.get("/users/{user_id}")
async def get_user(user_id: str):
    u = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(404, "غير موجود")
    return sanitize_user(u)


# ---------------- CLANS ----------------
async def _get_clan(clan_id: str) -> dict:
    c = await db.clans.find_one({"id": clan_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "الكلان غير موجود")
    return c


def _is_clan_staff(clan: dict, user: dict) -> bool:
    if is_staff(user):
        return True
    return user["id"] == clan["leader_id"] or user["id"] in clan.get("vice_leader_ids", [])


async def _leader_limits(clan: dict) -> tuple[int, int]:
    leader = await db.users.find_one({"id": clan["leader_id"]})
    plus = bool(leader and user_is_plus(leader))
    return (CLAN_LIMIT_PLUS if plus else CLAN_LIMIT_DEFAULT,
            VICE_LIMIT_PLUS if plus else VICE_LIMIT_DEFAULT)


@api.post("/clans")
async def create_clan(body: ClanCreateIn, user: dict = Depends(get_current_user)):
    if user.get("clan_id"):
        raise HTTPException(400, "أنت بالفعل في كلان")
    if await db.clans.find_one({"$or": [{"name": body.name}, {"tag": body.tag}]}):
        raise HTTPException(400, "اسم أو تاج الكلان مستخدم")
    clan = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "tag": body.tag,
        "description": body.description or "",
        "logo": None,
        "leader_id": user["id"],
        "vice_leader_ids": [],
        "member_ids": [user["id"]],
        "points": 0,
        "wins": 0,
        "losses": 0,
        "created_at": iso(now_utc()),
    }
    await db.clans.insert_one(clan)
    await db.users.update_one({"id": user["id"]}, {"$set": {"clan_id": clan["id"]}})
    clan.pop("_id", None)
    return clan


@api.get("/clans")
async def list_clans(q: str = ""):
    query = {"archived": {"$ne": True}}
    if q:
        query = {"$and": [
            query,
            {"$or": [
                {"name": {"$regex": q, "$options": "i"}},
                {"tag": {"$regex": q, "$options": "i"}},
            ]},
        ]}
    clans = await db.clans.find(query, {"_id": 0}).sort("points", -1).to_list(100)
    return clans


@api.get("/clans/{clan_id}")
async def get_clan_detail(clan_id: str):
    clan = await _get_clan(clan_id)
    member_ids = clan.get("member_ids", [])
    members_docs = await db.users.find({"id": {"$in": member_ids}}, {"_id": 0}).to_list(200)
    clan["members"] = [sanitize_user(m) for m in members_docs]
    max_members, max_vices = await _leader_limits(clan)
    clan["max_members"] = max_members
    clan["max_vices"] = max_vices
    return clan


@api.delete("/clans/{clan_id}")
async def delete_clan(clan_id: str, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if user["id"] != clan["leader_id"] and not is_staff(user):
        raise HTTPException(403, "ليس لديك صلاحية")
    await db.users.update_many({"clan_id": clan_id}, {"$set": {"clan_id": None}})
    await db.clans.delete_one({"id": clan_id})
    return {"ok": True}


@api.post("/clans/{clan_id}/join-request")
async def request_join(clan_id: str, user: dict = Depends(get_current_user)):
    if user.get("clan_id"):
        raise HTTPException(400, "أنت بالفعل في كلان")
    _assert_no_cooldown(user)
    _assert_act_set(user)
    clan = await _get_clan(clan_id)
    max_members, _ = await _leader_limits(clan)
    if len(clan.get("member_ids", [])) >= max_members:
        raise HTTPException(400, "الكلان ممتلئ")
    existing = await db.join_requests.find_one({"clan_id": clan_id, "user_id": user["id"], "status": "pending"})
    if existing:
        raise HTTPException(400, "طلبك قيد المراجعة")
    req = {
        "id": str(uuid.uuid4()),
        "clan_id": clan_id,
        "user_id": user["id"],
        "username": user["username"],
        "status": "pending",
        "type": "request",
        "created_at": iso(now_utc()),
    }
    await db.join_requests.insert_one(req)
    req.pop("_id", None)
    return req


@api.get("/clans/{clan_id}/requests")
async def list_requests(clan_id: str, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if not _is_clan_staff(clan, user):
        raise HTTPException(403, "ليس لديك صلاحية")
    reqs = await db.join_requests.find({"clan_id": clan_id, "status": "pending"}, {"_id": 0}).to_list(100)
    return reqs


@api.post("/clans/{clan_id}/requests/{req_id}")
async def handle_request(clan_id: str, req_id: str, body: HandleRequestIn, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if not _is_clan_staff(clan, user):
        raise HTTPException(403, "ليس لديك صلاحية")
    req = await db.join_requests.find_one({"id": req_id, "clan_id": clan_id}, {"_id": 0})
    if not req:
        raise HTTPException(404, "الطلب غير موجود")
    if body.action == "accept":
        max_members, _ = await _leader_limits(clan)
        if len(clan.get("member_ids", [])) >= max_members:
            raise HTTPException(400, f"الكلان ممتلئ (الحد {max_members})")
        target = await db.users.find_one({"id": req["user_id"]})
        if target and not target.get("clan_id"):
            _assert_no_cooldown(target)
            _assert_act_set(target)
            await db.users.update_one(
                {"id": req["user_id"]},
                {"$set": {"clan_id": clan_id, "clan_cooldown_until": None}},
            )
            await db.clans.update_one({"id": clan_id}, {"$addToSet": {"member_ids": req["user_id"]}})
            granted = await _maybe_grant_full_clan_reward(clan_id)
    await db.join_requests.update_one({"id": req_id}, {"$set": {"status": body.action}})
    return {"ok": True, "reward_granted": bool(locals().get("granted"))}


@api.post("/clans/{clan_id}/invite")
async def invite_player(clan_id: str, body: InviteIn, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if not _is_clan_staff(clan, user):
        raise HTTPException(403, "ليس لديك صلاحية")
    target = await db.users.find_one({"id": body.user_id})
    if not target:
        raise HTTPException(404, "اللاعب غير موجود")
    if target.get("clan_id"):
        raise HTTPException(400, "اللاعب في كلان آخر")
    max_members, _ = await _leader_limits(clan)
    if len(clan.get("member_ids", [])) >= max_members:
        raise HTTPException(400, "الكلان ممتلئ")
    inv = {
        "id": str(uuid.uuid4()),
        "clan_id": clan_id,
        "user_id": body.user_id,
        "username": target["username"],
        "status": "pending",
        "type": "invite",
        "created_at": iso(now_utc()),
    }
    await db.join_requests.insert_one(inv)
    inv.pop("_id", None)
    return inv


@api.get("/me/invites")
async def my_invites(user: dict = Depends(get_current_user)):
    invs = await db.join_requests.find(
        {"user_id": user["id"], "type": "invite", "status": "pending"}, {"_id": 0}
    ).to_list(100)
    for inv in invs:
        clan = await db.clans.find_one({"id": inv["clan_id"]}, {"_id": 0})
        if clan:
            inv["clan_name"] = clan["name"]
            inv["clan_tag"] = clan["tag"]
    return invs


@api.post("/invites/{inv_id}")
async def respond_invite(inv_id: str, body: HandleRequestIn, user: dict = Depends(get_current_user)):
    inv = await db.join_requests.find_one({"id": inv_id, "user_id": user["id"], "type": "invite"}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "الدعوة غير موجودة")
    if body.action == "accept" and not user.get("clan_id"):
        _assert_no_cooldown(user)
        _assert_act_set(user)
        clan = await _get_clan(inv["clan_id"])
        max_members, _ = await _leader_limits(clan)
        if len(clan.get("member_ids", [])) >= max_members:
            raise HTTPException(400, "الكلان ممتلئ")
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"clan_id": inv["clan_id"], "clan_cooldown_until": None}},
        )
        await db.clans.update_one({"id": inv["clan_id"]}, {"$addToSet": {"member_ids": user["id"]}})
        granted = await _maybe_grant_full_clan_reward(inv["clan_id"])
    await db.join_requests.update_one({"id": inv_id}, {"$set": {"status": body.action}})
    return {"ok": True, "reward_granted": bool(locals().get("granted"))}


@api.post("/clans/{clan_id}/kick/{member_id}")
async def kick_member(clan_id: str, member_id: str, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if user["id"] != clan["leader_id"] and not is_staff(user):
        raise HTTPException(403, "فقط القائد أو المنظم")
    if member_id == clan["leader_id"]:
        raise HTTPException(400, "لا يمكن طرد القائد")
    await db.clans.update_one({"id": clan_id}, {
        "$pull": {"member_ids": member_id, "vice_leader_ids": member_id}
    })
    await _start_clan_leave_cooldown(member_id)
    return {"ok": True}


@api.post("/clans/{clan_id}/promote/{member_id}")
async def promote_vice(clan_id: str, member_id: str, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if user["id"] != clan["leader_id"] and not is_staff(user):
        raise HTTPException(403, "ليس لديك صلاحية")
    if member_id not in clan["member_ids"]:
        raise HTTPException(400, "ليس عضواً")
    vices = clan.get("vice_leader_ids", [])
    _, max_vices = await _leader_limits(clan)
    if member_id in vices:
        await db.clans.update_one({"id": clan_id}, {"$pull": {"vice_leader_ids": member_id}})
    else:
        if len(vices) >= max_vices:
            raise HTTPException(400, f"الحد الأقصى للنواب {max_vices}. ترقى للـ Plus لزيادتها")
        await db.clans.update_one({"id": clan_id}, {"$addToSet": {"vice_leader_ids": member_id}})
    return {"ok": True}


@api.post("/clans/{clan_id}/leave")
async def leave_clan(clan_id: str, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if user["id"] == clan["leader_id"]:
        raise HTTPException(400, "القائد لا يمكنه المغادرة، احذف الكلان أولاً")
    await db.clans.update_one({"id": clan_id}, {
        "$pull": {"member_ids": user["id"], "vice_leader_ids": user["id"]}
    })
    await _start_clan_leave_cooldown(user["id"])
    return {"ok": True, "cooldown_hours": CLAN_LEAVE_COOLDOWN_HOURS}


# ---------------- CLAN CHALLENGES (request → accept → match) ----------------
@api.post("/clans/{clan_id}/challenge")
async def create_challenge(clan_id: str, body: ChallengeIn, user: dict = Depends(get_current_user)):
    """Leader/Vice of *user's* clan issues a challenge request to another clan.
    `clan_id` in the URL is the challenger's own clan id (must match user.clan_id)."""
    challenger = await _get_clan(clan_id)
    if not _is_clan_staff(challenger, user):
        raise HTTPException(403, "فقط قائد أو نائب الكلان")
    if user.get("clan_id") != clan_id and not is_staff(user):
        raise HTTPException(403, "هذا ليس كلانك")
    if body.opponent_clan_id == clan_id:
        raise HTTPException(400, "لا يمكن تحدي نفس الكلان")
    opponent = await _get_clan(body.opponent_clan_id)
    _assert_clan_can_match(challenger)
    _assert_clan_can_match(opponent)
    await _check_match_pair_cooldown(clan_id, opponent["id"])
    existing = await db.challenges.find_one({
        "status": "pending",
        "$or": [
            {"challenger_clan_id": clan_id, "opponent_clan_id": opponent["id"]},
            {"challenger_clan_id": opponent["id"], "opponent_clan_id": clan_id},
        ],
    })
    if existing:
        raise HTTPException(400, "هناك طلب تحدٍ معلّق بالفعل بين الكلانين")
    ch = {
        "id": str(uuid.uuid4()),
        "challenger_clan_id": clan_id,
        "challenger_name": challenger["name"],
        "challenger_tag": challenger["tag"],
        "opponent_clan_id": opponent["id"],
        "opponent_name": opponent["name"],
        "opponent_tag": opponent["tag"],
        "notes": body.notes or "",
        "status": "pending",
        "created_by": user["id"],
        "created_at": iso(now_utc()),
        "match_id": None,
    }
    await db.challenges.insert_one(ch)
    ch.pop("_id", None)
    return ch


@api.get("/clans/{clan_id}/challenges")
async def list_clan_challenges(clan_id: str, user: dict = Depends(get_current_user)):
    """Pending challenges involving this clan (incoming + outgoing)."""
    clan = await _get_clan(clan_id)
    if not _is_clan_staff(clan, user):
        raise HTTPException(403, "فقط قائد/نائب الكلان أو المنظم")
    docs = await db.challenges.find({
        "status": "pending",
        "$or": [{"challenger_clan_id": clan_id}, {"opponent_clan_id": clan_id}],
    }, {"_id": 0}).sort("created_at", -1).to_list(50)
    return docs


@api.post("/challenges/{ch_id}")
async def respond_challenge(ch_id: str, body: HandleRequestIn, user: dict = Depends(get_current_user)):
    """Opponent leader/vice accepts (→ creates live match) or rejects the challenge."""
    ch = await db.challenges.find_one({"id": ch_id}, {"_id": 0})
    if not ch:
        raise HTTPException(404, "التحدي غير موجود")
    if ch["status"] != "pending":
        raise HTTPException(400, "تم الرد على هذا التحدي مسبقاً")
    opponent = await _get_clan(ch["opponent_clan_id"])
    if not _is_clan_staff(opponent, user):
        raise HTTPException(403, "فقط قائد/نائب الكلان الخصم يمكنه الرد")
    if body.action == "reject":
        await db.challenges.update_one({"id": ch_id}, {"$set": {"status": "rejected"}})
        return {"ok": True, "status": "rejected"}
    # Accept → enforce roster minimum + create live match
    challenger = await _get_clan(ch["challenger_clan_id"])
    _assert_clan_can_match(challenger)
    _assert_clan_can_match(opponent)
    await _check_match_pair_cooldown(ch["challenger_clan_id"], ch["opponent_clan_id"])
    maps = [
        {"index": i, "vote_a": None, "vote_b": None, "winner": None,
         "disputed": False, "admin_resolved": False,
         "grace_started_at": None, "grace_started_by_clan": None,
         "prayer_started_at": None, "prayer_started_by_clan": None,
         "prayer_used_by_clan": []}
        for i in range(BO_TOTAL)
    ]
    m = {
        "id": str(uuid.uuid4()),
        "clan_a_id": ch["challenger_clan_id"],
        "clan_b_id": ch["opponent_clan_id"],
        "game": "Call of Duty",
        "status": "live",
        "maps": maps,
        "score_a": 0,
        "score_b": 0,
        "winner_clan_id": None,
        "notes": ch.get("notes", ""),
        "created_at": iso(now_utc()),
        "finished_at": None,
    }
    await db.matches.insert_one(m)
    await db.challenges.update_one(
        {"id": ch_id}, {"$set": {"status": "accepted", "match_id": m["id"]}}
    )
    m.pop("_id", None)
    return {"ok": True, "status": "accepted", "match": await _enrich_match(m)}


# ---------------- MATCHES ----------------
async def _enrich_match(m: dict) -> dict:
    a = await db.clans.find_one({"id": m["clan_a_id"]}, {"_id": 0, "name": 1, "tag": 1, "id": 1})
    b = await db.clans.find_one({"id": m["clan_b_id"]}, {"_id": 0, "name": 1, "tag": 1, "id": 1})
    m["clan_a"] = a
    m["clan_b"] = b
    # Attach derived timer state for each map (consumed by frontend countdown UI)
    for mp in m.get("maps", []):
        mp["grace_state"] = _compute_grace_state(mp)
    return m


def _count_maps(maps: list) -> tuple[int, int]:
    return (
        sum(1 for mp in maps if mp.get("winner") and mp["winner"] == "A"),
        sum(1 for mp in maps if mp.get("winner") and mp["winner"] == "B"),
    )


POINTS_WIN = 3
POINTS_LOSS = -1
POINTS_WITHDRAW = -3

GRACE_PERIOD_SECONDS = 10 * 60  # 10-minute grace period to claim a map win
PRAYER_BREAK_SECONDS = 10 * 60  # 10-minute prayer break that pauses the grace timer
MATCH_PAIR_COOLDOWN_HOURS = 3   # Same two clans cannot match within 3 hours


async def _check_match_pair_cooldown(clan_a_id: str, clan_b_id: str) -> None:
    """Raises 400 if the two clans have a match (live or finished) within the cooldown window."""
    cutoff = iso(now_utc() - timedelta(hours=MATCH_PAIR_COOLDOWN_HOURS))
    pair = {"$or": [
        {"clan_a_id": clan_a_id, "clan_b_id": clan_b_id},
        {"clan_a_id": clan_b_id, "clan_b_id": clan_a_id},
    ]}
    # Live match in progress is always a block
    live = await db.matches.find_one({**pair, "status": "live"}, {"_id": 0, "id": 1, "created_at": 1})
    if live:
        raise HTTPException(400, "هناك مباراة جارية بالفعل بين الكلانين")
    # Recent finished match
    recent = await db.matches.find_one(
        {**pair, "status": "finished", "finished_at": {"$gte": cutoff}},
        {"_id": 0, "finished_at": 1},
        sort=[("finished_at", -1)],
    )
    if recent:
        try:
            ends = datetime.fromisoformat(recent["finished_at"]) + timedelta(hours=MATCH_PAIR_COOLDOWN_HOURS)
            remaining = (ends - now_utc()).total_seconds()
            mins = max(1, int((remaining + 59) // 60))
            hrs = mins // 60
            rem_mins = mins % 60
            label = f"{hrs} ساعة و{rem_mins} دقيقة" if hrs else f"{mins} دقيقة"
            raise HTTPException(400, f"يجب الانتظار {label} قبل لعب مباراة جديدة بين الكلانين")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(400, "الكلانان في فترة انتظار 3 ساعات")

# Video upload limits
PLUS_VIDEO_MAX_BYTES = 500 * 1024 * 1024     # 500 MB
FREE_VIDEO_MAX_BYTES = 100 * 1024 * 1024     # 100 MB
UPLOAD_DIR = ROOT_DIR / "uploads" / "videos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

async def _maybe_finish(match: dict):
    """If a team has won MAPS_TO_WIN maps, finalize match."""
    won_a, won_b = _count_maps(match["maps"])
    winner = None
    if won_a >= MAPS_TO_WIN:
        winner = match["clan_a_id"]
    elif won_b >= MAPS_TO_WIN:
        winner = match["clan_b_id"]
    if not winner:
        return
    if match.get("status") == "finished":
        return
    loser = match["clan_b_id"] if winner == match["clan_a_id"] else match["clan_a_id"]
    await db.matches.update_one({"id": match["id"]}, {"$set": {
        "status": "finished",
        "winner_clan_id": winner,
        "score_a": won_a,
        "score_b": won_b,
        "finished_at": iso(now_utc()),
    }})
    await db.clans.update_one({"id": winner}, {"$inc": {"wins": 1, "points": POINTS_WIN}})
    await db.clans.update_one({"id": loser}, {"$inc": {"losses": 1, "points": POINTS_LOSS}})
    # Career stats: increment player wins/losses for each active member of each side
    winner_clan = await db.clans.find_one({"id": winner}, {"_id": 0, "member_ids": 1})
    loser_clan = await db.clans.find_one({"id": loser}, {"_id": 0, "member_ids": 1})
    if winner_clan and winner_clan.get("member_ids"):
        await db.users.update_many({"id": {"$in": winner_clan["member_ids"]}}, {"$inc": {"wins": 1}})
    if loser_clan and loser_clan.get("member_ids"):
        await db.users.update_many({"id": {"$in": loser_clan["member_ids"]}}, {"$inc": {"losses": 1}})
    # If part of a tournament, advance bracket
    fresh_match = await db.matches.find_one({"id": match["id"]}, {"_id": 0})
    if fresh_match and fresh_match.get("tournament_id"):
        await _advance_tournament_winner(fresh_match, winner)


@api.post("/matches")
async def create_match(body: MatchCreateIn, user: dict = Depends(get_current_user)):
    a = await _get_clan(body.clan_a_id)
    b = await _get_clan(body.clan_b_id)
    if a["id"] == b["id"]:
        raise HTTPException(400, "لا يمكن تحدي نفس الكلان")
    if not is_staff(user) and user["id"] not in (a["leader_id"], b["leader_id"]):
        raise HTTPException(403, "فقط المنظم أو قادة الكلانات")
    # Staff may bypass the 3-hour pair cooldown (organizer override)
    if not is_staff(user):
        await _check_match_pair_cooldown(a["id"], b["id"])
    maps = [
        {"index": i, "vote_a": None, "vote_b": None, "winner": None,
         "disputed": False, "admin_resolved": False,
         "grace_started_at": None, "grace_started_by_clan": None,
         "prayer_started_at": None, "prayer_started_by_clan": None,
         "prayer_used_by_clan": []}
        for i in range(BO_TOTAL)
    ]
    m = {
        "id": str(uuid.uuid4()),
        "clan_a_id": body.clan_a_id,
        "clan_b_id": body.clan_b_id,
        "game": "Call of Duty",
        "status": "live",
        "maps": maps,
        "score_a": 0,
        "score_b": 0,
        "winner_clan_id": None,
        "notes": body.notes or "",
        "created_at": iso(now_utc()),
        "finished_at": None,
    }
    await db.matches.insert_one(m)
    m.pop("_id", None)
    return await _enrich_match(m)


@api.get("/matches/live")
async def live_matches():
    docs = await db.matches.find({"status": "live"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [await _enrich_match(d) for d in docs]


@api.get("/matches/history")
async def match_history():
    cutoff = iso(now_utc() - timedelta(hours=24))
    docs = await db.matches.find(
        {"status": "finished", "finished_at": {"$gte": cutoff}}, {"_id": 0}
    ).sort("finished_at", -1).to_list(200)
    return [await _enrich_match(d) for d in docs]


@api.get("/matches/{match_id}")
async def get_match(match_id: str):
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "غير موجود")
    return await _enrich_match(m)


def _resolve_vote_side(user: dict, staff_a: list, staff_b: list) -> str:
    """Determine which side ('vote_a'/'vote_b') the current user votes on."""
    if user["id"] in staff_a:
        return "vote_a"
    if user["id"] in staff_b:
        return "vote_b"
    if is_staff(user):
        raise HTTPException(400, "المنظم يستخدم admin-resolve-map")
    raise HTTPException(403, "ليس لديك صلاحية")


def _apply_map_vote(mp: dict, side: str, winner_label: str) -> dict:
    """Apply a vote on a single map; reconcile agreement/dispute. Returns updated mp."""
    mp[side] = winner_label
    if mp.get("vote_a") and mp.get("vote_b"):
        if mp["vote_a"] == mp["vote_b"]:
            mp["winner"] = mp["vote_a"]
            mp["disputed"] = False
        else:
            mp["disputed"] = True
            mp["winner"] = None
    return mp


def _is_match_prayer_active(match: dict) -> bool:
    pb = match.get("match_prayer_break")
    if not pb or pb.get("resumed"):
        return False
    ends_at = pb.get("ends_at")
    if not ends_at:
        return False
    try:
        return datetime.fromisoformat(ends_at) > now_utc()
    except Exception:
        return False


@api.post("/matches/{match_id}/vote-map")
async def vote_map(match_id: str, body: MapVoteIn, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")
    if _is_match_prayer_active(match):
        raise HTTPException(400, "بريك صلاة جارٍ — استأنف المباراة أولاً")
    if not (0 <= body.map_index < BO_TOTAL):
        raise HTTPException(400, "رقم ماب غير صحيح")
    if body.winner_clan_id not in (match["clan_a_id"], match["clan_b_id"]):
        raise HTTPException(400, "كلان غير صحيح")
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    staff_a = [a["leader_id"]] + a.get("vice_leader_ids", [])
    staff_b = [b["leader_id"]] + b.get("vice_leader_ids", [])
    side = _resolve_vote_side(user, staff_a, staff_b)
    mp = match["maps"][body.map_index]
    if mp.get("admin_resolved"):
        raise HTTPException(400, "هذا الماب أنهاه المنظم")
    winner_label = "A" if body.winner_clan_id == match["clan_a_id"] else "B"
    match["maps"][body.map_index] = _apply_map_vote(mp, side, winner_label)
    await db.matches.update_one({"id": match_id}, {"$set": {"maps": match["maps"]}})
    await _maybe_finish(match)
    fresh = await db.matches.find_one({"id": match_id}, {"_id": 0})
    return await _enrich_match(fresh)


@api.post("/matches/{match_id}/admin-resolve-map")
async def admin_resolve_map(match_id: str, body: AdminResolveMapIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")
    if not (0 <= body.map_index < BO_TOTAL):
        raise HTTPException(400, "رقم ماب غير صحيح")
    if body.winner_clan_id not in (match["clan_a_id"], match["clan_b_id"]):
        raise HTTPException(400, "كلان غير صحيح")
    mp = match["maps"][body.map_index]
    mp["winner"] = "A" if body.winner_clan_id == match["clan_a_id"] else "B"
    mp["disputed"] = False
    mp["admin_resolved"] = True
    match["maps"][body.map_index] = mp
    await db.matches.update_one({"id": match_id}, {"$set": {"maps": match["maps"]}})
    await _maybe_finish(match)
    fresh = await db.matches.find_one({"id": match_id}, {"_id": 0})
    return await _enrich_match(fresh)


@api.post("/matches/{match_id}/dispute")
async def dispute_match(match_id: str, user: dict = Depends(get_current_user)):
    """Trigger admin attention. Marks last incomplete map as disputed."""
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    if user["id"] not in [a["leader_id"], b["leader_id"]] + a.get("vice_leader_ids", []) + b.get("vice_leader_ids", []):
        raise HTTPException(403, "للقادة فقط")
    for mp in match["maps"]:
        if not mp.get("winner") and not mp.get("admin_resolved"):
            mp["disputed"] = True
            break
    await db.matches.update_one({"id": match_id}, {"$set": {"maps": match["maps"]}})
    return {"ok": True}


async def _finalize_withdrawal(match_id: str, withdrawing_clan: str, winning_clan: str, won_a: int, won_b: int) -> None:
    """Apply DB updates for a withdrawal: match state, points, system chat message."""
    await db.matches.update_one({"id": match_id}, {"$set": {
        "status": "finished",
        "winner_clan_id": winning_clan,
        "withdrawn_clan_id": withdrawing_clan,
        "score_a": won_a,
        "score_b": won_b,
        "finished_at": iso(now_utc()),
    }})
    await db.clans.update_one({"id": winning_clan}, {"$inc": {"wins": 1, "points": POINTS_WIN}})
    await db.clans.update_one({"id": withdrawing_clan}, {"$inc": {"losses": 1, "points": POINTS_WITHDRAW}})
    # Career stats for individual players
    w_clan = await db.clans.find_one({"id": winning_clan}, {"_id": 0, "member_ids": 1})
    l_clan = await db.clans.find_one({"id": withdrawing_clan}, {"_id": 0, "member_ids": 1})
    if w_clan and w_clan.get("member_ids"):
        await db.users.update_many({"id": {"$in": w_clan["member_ids"]}}, {"$inc": {"wins": 1}})
    if l_clan and l_clan.get("member_ids"):
        await db.users.update_many({"id": {"$in": l_clan["member_ids"]}}, {"$inc": {"losses": 1}})
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "user_id": "system",
        "username": "النظام",
        "user_role": "admin",
        "user_clan_id": None,
        "type": "text",
        "text": "⚠️ انسحب الكلان من المباراة. الفوز للخصم.",
        "image": None, "video": None,
        "opponent_decision": None, "admin_decision": None, "admin_note": "",
        "created_at": iso(now_utc()),
    })


@api.post("/matches/{match_id}/withdraw")
async def withdraw_match(match_id: str, user: dict = Depends(get_current_user)):
    """Clan leader/vice withdraws their clan from a live match (-3 pts, opponent +3)."""
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    staff_a = [a["leader_id"]] + a.get("vice_leader_ids", [])
    staff_b = [b["leader_id"]] + b.get("vice_leader_ids", [])
    withdrawing_clan: str
    winning_clan: str
    if user["id"] in staff_a:
        withdrawing_clan, winning_clan = a["id"], b["id"]
    elif user["id"] in staff_b:
        withdrawing_clan, winning_clan = b["id"], a["id"]
    else:
        raise HTTPException(403, "فقط القائد أو نوابه يستطيع الانسحاب")
    won_a, won_b = _count_maps(match["maps"])
    await _finalize_withdrawal(match_id, withdrawing_clan, winning_clan, won_a, won_b)
    if match.get("tournament_id"):
        fresh_match = await db.matches.find_one({"id": match_id}, {"_id": 0})
        if fresh_match:
            await _advance_tournament_winner(fresh_match, winning_clan)
    return {"ok": True, "withdrawn_clan_id": withdrawing_clan, "winning_clan_id": winning_clan}


# ---------------- MAP TIMERS (Grace period + Prayer break) ----------------
def _user_side(user: dict, a: dict, b: dict) -> Optional[str]:
    """Returns 'A', 'B', or None depending on which clan's staff this user belongs to."""
    staff_a = [a["leader_id"]] + a.get("vice_leader_ids", [])
    staff_b = [b["leader_id"]] + b.get("vice_leader_ids", [])
    if user["id"] in staff_a:
        return "A"
    if user["id"] in staff_b:
        return "B"
    return None


def _other(side: str) -> str:
    return "B" if side == "A" else "A"


def _compute_grace_state(mp: dict) -> dict:
    """Pure helper returning derived timing info for a map."""
    g_at = mp.get("grace_started_at")
    if not g_at:
        return {"active": False, "ends_at": None, "paused": False, "started_by": None}
    try:
        start = datetime.fromisoformat(g_at)
    except Exception:
        return {"active": False, "ends_at": None, "paused": False, "started_by": None}
    used = len(mp.get("prayer_used_by_clan", []))
    ends_at = start + timedelta(seconds=GRACE_PERIOD_SECONDS + used * PRAYER_BREAK_SECONDS)
    # If a prayer is currently active, freeze countdown (extend ends_at proportionally)
    p_at = mp.get("prayer_started_at")
    paused = False
    if p_at:
        try:
            p_start = datetime.fromisoformat(p_at)
            if (now_utc() - p_start).total_seconds() < PRAYER_BREAK_SECONDS:
                paused = True
        except Exception:
            pass
    return {
        "active": True,
        "ends_at": iso(ends_at),
        "paused": paused,
        "started_by": mp.get("grace_started_by_clan"),
    }


@api.post("/matches/{match_id}/maps/{map_index}/grace")
async def start_grace(match_id: str, map_index: int, user: dict = Depends(get_current_user)):
    """Caller's clan claims that the opponent has gone AFK on this map.
    Starts a 10-min countdown. If opponent doesn't vote in time, claimer can claim the win."""
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")
    if not (0 <= map_index < BO_TOTAL):
        raise HTTPException(400, "رقم ماب غير صحيح")
    mp = match["maps"][map_index]
    if mp.get("winner") or mp.get("admin_resolved"):
        raise HTTPException(400, "هذا الماب محسوم")
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    side = _user_side(user, a, b)
    if not side:
        raise HTTPException(403, "فقط القائد أو النواب")
    if mp.get("grace_started_at"):
        raise HTTPException(400, "المهلة بدأت بالفعل")
    mp["grace_started_at"] = iso(now_utc())
    mp["grace_started_by_clan"] = side
    match["maps"][map_index] = mp
    await db.matches.update_one({"id": match_id}, {"$set": {"maps": match["maps"]}})
    fresh = await db.matches.find_one({"id": match_id}, {"_id": 0})
    return await _enrich_match(fresh)


@api.post("/matches/{match_id}/maps/{map_index}/prayer")
async def start_prayer(match_id: str, map_index: int, user: dict = Depends(get_current_user)):
    """The clan being claimed against starts a one-time 10-min prayer break that pauses the grace."""
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")
    if not (0 <= map_index < BO_TOTAL):
        raise HTTPException(400, "رقم ماب غير صحيح")
    mp = match["maps"][map_index]
    if mp.get("winner") or mp.get("admin_resolved"):
        raise HTTPException(400, "هذا الماب محسوم")
    if not mp.get("grace_started_at"):
        raise HTTPException(400, "لا توجد مهلة جارية")
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    side = _user_side(user, a, b)
    if not side:
        raise HTTPException(403, "فقط القائد أو النواب")
    used = mp.get("prayer_used_by_clan", [])
    if side in used:
        raise HTTPException(400, "استخدمت استراحة الصلاة مسبقاً في هذا الماب")
    # Check if a prayer is currently active
    p_at = mp.get("prayer_started_at")
    if p_at:
        try:
            p_start = datetime.fromisoformat(p_at)
            if (now_utc() - p_start).total_seconds() < PRAYER_BREAK_SECONDS:
                raise HTTPException(400, "هناك استراحة صلاة جارية")
        except Exception:
            pass
    mp["prayer_started_at"] = iso(now_utc())
    mp["prayer_started_by_clan"] = side
    mp["prayer_used_by_clan"] = used + [side]
    match["maps"][map_index] = mp
    await db.matches.update_one({"id": match_id}, {"$set": {"maps": match["maps"]}})
    fresh = await db.matches.find_one({"id": match_id}, {"_id": 0})
    return await _enrich_match(fresh)


@api.post("/matches/{match_id}/maps/{map_index}/claim-grace-win")
async def claim_grace_win(match_id: str, map_index: int, user: dict = Depends(get_current_user)):
    """After grace period expires, the claimer's clan auto-wins this map."""
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")
    if not (0 <= map_index < BO_TOTAL):
        raise HTTPException(400, "رقم ماب غير صحيح")
    mp = match["maps"][map_index]
    if mp.get("winner") or mp.get("admin_resolved"):
        raise HTTPException(400, "هذا الماب محسوم")
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    side = _user_side(user, a, b)
    if not side:
        raise HTTPException(403, "فقط القائد أو النواب")
    if mp.get("grace_started_by_clan") != side:
        raise HTTPException(403, "فقط الكلان الذي بدأ المهلة يمكنه المطالبة بالفوز")
    state = _compute_grace_state(mp)
    if state["paused"]:
        raise HTTPException(400, "استراحة صلاة جارية")
    if not state["ends_at"]:
        raise HTTPException(400, "لم تبدأ المهلة")
    if datetime.fromisoformat(state["ends_at"]) > now_utc():
        raise HTTPException(400, "لم تنته المهلة بعد")
    mp["winner"] = side
    mp["admin_resolved"] = False
    match["maps"][map_index] = mp
    await db.matches.update_one({"id": match_id}, {"$set": {"maps": match["maps"]}})
    await _maybe_finish(match)
    fresh = await db.matches.find_one({"id": match_id}, {"_id": 0})
    return await _enrich_match(fresh)


# ---------------- CHAT ----------------
async def _chat_perms(match: dict, user: dict):
    """Returns (can_view_text, can_write, can_admin_moderate, role_label, is_opponent_leader_for_msg)."""
    is_admin = is_staff(user)
    a = await db.clans.find_one({"id": match["clan_a_id"]})
    b = await db.clans.find_one({"id": match["clan_b_id"]})
    if not a or not b:
        return (False, False, False, None, False)
    staff_a = [a["leader_id"]] + a.get("vice_leader_ids", [])
    staff_b = [b["leader_id"]] + b.get("vice_leader_ids", [])
    is_player_in_match = user.get("clan_id") in (match["clan_a_id"], match["clan_b_id"])
    can_view_text = is_admin or is_player_in_match
    can_write = is_admin or user["id"] in staff_a or user["id"] in staff_b
    return can_view_text, can_write, is_admin, staff_a, staff_b


@api.get("/matches/{match_id}/chat")
async def get_chat(match_id: str, user: dict = Depends(get_current_user)):
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "غير موجود")
    is_admin = is_staff(user)
    a = await _get_clan(m["clan_a_id"])
    b = await _get_clan(m["clan_b_id"])
    is_in_match = user.get("clan_id") in (m["clan_a_id"], m["clan_b_id"])
    is_logged_in = bool(user)
    # Outsider clans CAN view media-only; otherwise media + text.
    if not is_logged_in:
        raise HTTPException(403, "سجل دخول")
    msgs = await db.chat_messages.find({"match_id": match_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    filtered = []
    for msg in msgs:
        if is_admin or is_in_match:
            filtered.append(msg)
        else:
            # Outsider: hide text-only; for media: hide the text but keep image/video
            if msg.get("image") or msg.get("video"):
                copy = {**msg, "text": ""}
                filtered.append(copy)
    can_write = is_admin or user["id"] in [a["leader_id"]] + a.get("vice_leader_ids", []) + [b["leader_id"]] + b.get("vice_leader_ids", [])
    user_clan = user.get("clan_id")
    return {
        "messages": filtered,
        "can_write": can_write,
        "user_clan_id": user_clan,
        "is_admin": is_admin,
    }


def _classify_message_type(body: ChatMessageIn) -> str:
    if body.video:
        return "video"
    if body.image:
        return "image"
    return "text"


def _determine_chat_role(user: dict, a: dict, b: dict) -> str:
    if is_staff(user):
        return "admin"
    if user["id"] == a["leader_id"] or user["id"] == b["leader_id"]:
        return "leader"
    return "vice"


def _build_chat_message(body: ChatMessageIn, user: dict, match_id: str, role: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "user_id": user["id"],
        "username": user["username"],
        "user_role": role,
        "user_clan_id": user.get("clan_id"),
        "type": _classify_message_type(body),
        "text": body.text or "",
        "image": body.image,
        "video": body.video,
        "opponent_decision": None,
        "admin_decision": None,
        "admin_note": "",
        "created_at": iso(now_utc()),
    }


@api.post("/matches/{match_id}/chat")
async def post_chat(match_id: str, body: ChatMessageIn, user: dict = Depends(get_current_user)):
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "غير موجود")
    if not body.text and not body.image and not body.video:
        raise HTTPException(400, "الرسالة فارغة")
    a = await db.clans.find_one({"id": m["clan_a_id"]})
    b = await db.clans.find_one({"id": m["clan_b_id"]})
    staff_a = [a["leader_id"]] + a.get("vice_leader_ids", [])
    staff_b = [b["leader_id"]] + b.get("vice_leader_ids", [])
    is_admin = is_staff(user)
    if not (is_admin or user["id"] in staff_a or user["id"] in staff_b):
        raise HTTPException(403, "لا يمكنك الكتابة في هذا الشات")
    msg = _build_chat_message(body, user, match_id, _determine_chat_role(user, a, b))
    await db.chat_messages.insert_one(msg)
    msg.pop("_id", None)
    return msg


@api.post("/chat/{msg_id}/opponent-decision")
async def opponent_decision(msg_id: str, body: OpponentImageDecisionIn, user: dict = Depends(get_current_user)):
    """Opposing clan leader confirms or rejects the image (result screenshot)."""
    msg = await db.chat_messages.find_one({"id": msg_id}, {"_id": 0})
    if not msg:
        raise HTTPException(404, "غير موجود")
    if msg.get("type") != "image":
        raise HTTPException(400, "ليس صورة")
    match = await db.matches.find_one({"id": msg["match_id"]}, {"_id": 0})
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    uploader_clan = msg.get("user_clan_id")
    # opposing side leader/vice can decide; not own clan
    leaders_a = [a["leader_id"]] + a.get("vice_leader_ids", [])
    leaders_b = [b["leader_id"]] + b.get("vice_leader_ids", [])
    if uploader_clan == a["id"]:
        allowed = leaders_b
    elif uploader_clan == b["id"]:
        allowed = leaders_a
    else:
        allowed = leaders_a + leaders_b  # admin uploads — both sides could review
    if user["id"] not in allowed:
        raise HTTPException(403, "هذه الصورة ليست لمراجعتك")
    await db.chat_messages.update_one({"id": msg_id}, {"$set": {"opponent_decision": body.decision}})
    return {"ok": True}


@api.post("/chat/{msg_id}/admin-decision")
async def admin_chat_decision(msg_id: str, body: AdminMediaDecisionIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    msg = await db.chat_messages.find_one({"id": msg_id})
    if not msg:
        raise HTTPException(404, "غير موجود")
    update = {"admin_decision": body.decision, "admin_note": body.note or ""}
    await db.chat_messages.update_one({"id": msg_id}, {"$set": update})
    return {"ok": True}


# ---------------- LEADERBOARD ----------------
@api.get("/leaderboard/clans")
async def leaderboard_clans():
    docs = await db.clans.find(
        {"archived": {"$ne": True}},
        {"_id": 0, "id": 1, "name": 1, "tag": 1, "points": 1, "wins": 1, "losses": 1, "trophies": 1}
    ).sort("points", -1).limit(50).to_list(50)
    return docs


@api.get("/leaderboard/players")
async def leaderboard_players():
    docs = await db.users.find({"role": {"$ne": "admin"}}, {"_id": 0}).sort("points", -1).limit(50).to_list(50)
    return [sanitize_user(d) for d in docs]


# ---------------- RULES ----------------
@api.get("/rules")
async def list_rules():
    return await db.rules.find({}, {"_id": 0}).sort("order", 1).to_list(100)


@api.post("/rules")
async def create_rule(body: RuleIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    rule = {"id": str(uuid.uuid4()), **body.model_dump(), "created_at": iso(now_utc())}
    await db.rules.insert_one(rule)
    rule.pop("_id", None)
    return rule


@api.put("/rules/{rule_id}")
async def update_rule(rule_id: str, body: RuleIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    await db.rules.update_one({"id": rule_id}, {"$set": body.model_dump()})
    r = await db.rules.find_one({"id": rule_id}, {"_id": 0})
    return r


@api.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    await db.rules.delete_one({"id": rule_id})
    return {"ok": True}


# ---------------- ROLES (Owner only) ----------------
class RoleChangeIn(BaseModel):
    role: Literal["admin", "player"]


@api.get("/admin/users")
async def admin_list_users(user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    docs = await db.users.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [sanitize_user(d) for d in docs]


@api.post("/admin/users/{user_id}/role")
async def change_user_role(user_id: str, body: RoleChangeIn, user: dict = Depends(get_current_user)):
    if not is_owner(user):
        raise HTTPException(403, "للمالك فقط")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "المستخدم غير موجود")
    if target.get("role") == "owner":
        raise HTTPException(400, "لا يمكن تغيير دور المالك")
    await db.users.update_one({"id": user_id}, {"$set": {"role": body.role}})
    return {"ok": True, "role": body.role}


# ---------------- TOURNAMENTS (Single Elimination) ----------------
class TournamentCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: Optional[str] = ""
    rules: Optional[str] = ""
    max_participants: int = Field(ge=2, le=16)  # 2,4,8,12,16
    losers_bracket: bool = False  # Optional double-elim (UI flag)


def _next_power_of_2(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


def _build_initial_bracket(clan_ids: list) -> list:
    """Single-elimination bracket. Pads to next power of 2 with byes."""
    import random
    shuffled = clan_ids.copy()
    random.shuffle(shuffled)
    size = max(2, _next_power_of_2(len(shuffled)))
    while len(shuffled) < size:
        shuffled.append(None)
    rounds = []
    r1 = []
    for i in range(0, size, 2):
        a_id, b_id = shuffled[i], shuffled[i + 1]
        slot = {"clan_a_id": a_id, "clan_b_id": b_id, "winner_id": None, "match_id": None}
        # Bye handling: lone side auto-wins
        if a_id and not b_id:
            slot["winner_id"] = a_id
        elif b_id and not a_id:
            slot["winner_id"] = b_id
        r1.append(slot)
    rounds.append(r1)
    n = len(r1)
    while n > 1:
        n //= 2
        rounds.append([
            {"clan_a_id": None, "clan_b_id": None, "winner_id": None, "match_id": None}
            for _ in range(n)
        ])
    # Propagate byes from round 1 → round 2
    if len(rounds) > 1:
        for i, slot in enumerate(rounds[0]):
            if slot["winner_id"]:
                next_slot = i // 2
                side = "clan_a_id" if i % 2 == 0 else "clan_b_id"
                rounds[1][next_slot][side] = slot["winner_id"]
    return rounds


async def _create_round_matches(tournament: dict, round_index: int) -> None:
    """Create live Match records for round `round_index` of the tournament."""
    rnd = tournament["bracket"][round_index]
    for slot_index, slot in enumerate(rnd):
        if slot.get("match_id") or slot.get("winner_id"):
            continue  # already created or already decided (bye)
        a_id = slot.get("clan_a_id")
        b_id = slot.get("clan_b_id")
        if not a_id or not b_id:
            continue
        maps = [
            {"index": i, "vote_a": None, "vote_b": None, "winner": None,
             "disputed": False, "admin_resolved": False,
             "grace_started_at": None, "grace_started_by_clan": None,
             "prayer_started_at": None, "prayer_started_by_clan": None,
             "prayer_used_by_clan": []}
            for i in range(BO_TOTAL)
        ]
        m = {
            "id": str(uuid.uuid4()),
            "clan_a_id": a_id,
            "clan_b_id": b_id,
            "game": "Call of Duty",
            "status": "live",
            "maps": maps,
            "score_a": 0, "score_b": 0,
            "winner_clan_id": None,
            "notes": f"Tournament: {tournament['name']} • Round {round_index + 1}",
            "tournament_id": tournament["id"],
            "tournament_round": round_index,
            "tournament_slot": slot_index,
            "created_at": iso(now_utc()),
            "finished_at": None,
        }
        await db.matches.insert_one(m)
        slot["match_id"] = m["id"]
    await db.tournaments.update_one(
        {"id": tournament["id"]},
        {"$set": {f"bracket.{round_index}": rnd}}
    )


async def _advance_tournament_winner(match: dict, winner_id: str) -> None:
    """Called when a tournament match finishes. Advance winner to next round."""
    tid = match.get("tournament_id")
    if not tid:
        return
    tournament = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not tournament:
        return
    r_idx = match.get("tournament_round")
    s_idx = match.get("tournament_slot")
    if r_idx is None or s_idx is None:
        return
    tournament["bracket"][r_idx][s_idx]["winner_id"] = winner_id
    # Move to next round
    if r_idx + 1 < len(tournament["bracket"]):
        next_slot = s_idx // 2
        side = "clan_a_id" if s_idx % 2 == 0 else "clan_b_id"
        tournament["bracket"][r_idx + 1][next_slot][side] = winner_id
        await db.tournaments.update_one(
            {"id": tid}, {"$set": {"bracket": tournament["bracket"]}}
        )
        # If both sides of the next slot are filled, create that match
        ns = tournament["bracket"][r_idx + 1][next_slot]
        if ns.get("clan_a_id") and ns.get("clan_b_id") and not ns.get("match_id"):
            await _create_round_matches(tournament, r_idx + 1)
    else:
        # Final round — champion
        await db.tournaments.update_one(
            {"id": tid},
            {"$set": {"bracket": tournament["bracket"], "status": "finished",
                      "champion_clan_id": winner_id, "finished_at": iso(now_utc())}}
        )
        # Grant trophy to the champion clan
        await db.clans.update_one(
            {"id": winner_id},
            {"$push": {"trophies": {
                "id": str(uuid.uuid4()),
                "kind": "tournament",
                "label": f"بطل بطولة {tournament['name']}",
                "tournament_id": tid,
                "awarded_at": iso(now_utc()),
            }}}
        )


@api.get("/tournaments")
async def list_tournaments():
    docs = await db.tournaments.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs


async def _enrich_tournament(t: dict) -> dict:
    """Resolve clan info for bracket display."""
    ids = set()
    for rnd in t.get("bracket", []):
        for s in rnd:
            for k in ("clan_a_id", "clan_b_id", "winner_id"):
                if s.get(k):
                    ids.add(s[k])
    for cid in t.get("participants", []):
        ids.add(cid)
    if t.get("champion_clan_id"):
        ids.add(t["champion_clan_id"])
    clan_docs = await db.clans.find(
        {"id": {"$in": list(ids)}}, {"_id": 0, "id": 1, "name": 1, "tag": 1}
    ).to_list(200) if ids else []
    t["clans"] = {c["id"]: c for c in clan_docs}
    return t


@api.get("/tournaments/{tid}")
async def get_tournament(tid: str):
    t = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "البطولة غير موجودة")
    return await _enrich_tournament(t)


@api.post("/tournaments")
async def create_tournament(body: TournamentCreateIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    if body.max_participants not in (2, 4, 8, 12, 16):
        raise HTTPException(400, "العدد يجب أن يكون 2, 4, 8, 12 أو 16")
    now = now_utc()
    t = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "description": body.description or "",
        "rules": body.rules or "",
        "max_participants": body.max_participants,
        "losers_bracket": bool(body.losers_bracket),
        "status": "registration",  # registration → live → finished
        "starts_at": iso(now),
        "plus_window_until": iso(now + timedelta(hours=24)),
        "participants": [],
        "bracket": [],
        "champion_clan_id": None,
        "created_by": user["id"],
        "created_at": iso(now),
        "finished_at": None,
    }
    await db.tournaments.insert_one(t)
    t.pop("_id", None)
    return await _enrich_tournament(t)


@api.delete("/tournaments/{tid}")
async def delete_tournament(tid: str, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    t = await db.tournaments.find_one({"id": tid})
    if not t:
        raise HTTPException(404, "غير موجودة")
    # Cancel any live matches
    await db.matches.update_many(
        {"tournament_id": tid, "status": "live"},
        {"$set": {"status": "finished", "finished_at": iso(now_utc())}}
    )
    await db.tournaments.delete_one({"id": tid})
    return {"ok": True}


@api.post("/tournaments/{tid}/join")
async def join_tournament(tid: str, user: dict = Depends(get_current_user)):
    t = await db.tournaments.find_one({"id": tid})
    if not t:
        raise HTTPException(404, "البطولة غير موجودة")
    if t["status"] != "registration":
        raise HTTPException(400, "التسجيل مغلق")
    if not user.get("clan_id"):
        raise HTTPException(400, "يجب أن تكون قائد كلان")
    clan = await db.clans.find_one({"id": user["clan_id"]}, {"_id": 0})
    if not clan or clan["leader_id"] != user["id"]:
        raise HTTPException(403, "فقط القائد يسجل الكلان")
    if clan["id"] in t.get("participants", []):
        raise HTTPException(400, "كلانك مسجل بالفعل")
    if len(t.get("participants", [])) >= t["max_participants"]:
        raise HTTPException(400, "البطولة ممتلئة")
    # Plus window enforcement
    leader = await db.users.find_one({"id": clan["leader_id"]})
    plus = user_is_plus(leader) if leader else False
    try:
        plus_until = datetime.fromisoformat(t["plus_window_until"])
    except Exception:
        plus_until = now_utc()
    if not plus and now_utc() < plus_until:
        raise HTTPException(400, "أول 24 ساعة للكلانات Plus فقط")
    await db.tournaments.update_one(
        {"id": tid}, {"$addToSet": {"participants": clan["id"]}}
    )
    return {"ok": True}


@api.post("/tournaments/{tid}/start")
async def start_tournament(tid: str, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    t = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "غير موجودة")
    if t["status"] != "registration":
        raise HTTPException(400, "البطولة بدأت بالفعل")
    if len(t.get("participants", [])) < 2:
        raise HTTPException(400, "يجب كلانَين على الأقل")
    bracket = _build_initial_bracket(t["participants"])
    await db.tournaments.update_one({"id": tid}, {"$set": {
        "bracket": bracket, "status": "live"
    }})
    fresh = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    await _create_round_matches(fresh, 0)
    # If first round had byes propagating directly into round 2 with both sides filled, create them
    if len(fresh["bracket"]) > 1:
        for slot_idx, slot in enumerate(fresh["bracket"][1]):
            if slot.get("clan_a_id") and slot.get("clan_b_id") and not slot.get("match_id"):
                await _create_round_matches(fresh, 1)
                break
    final = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    return await _enrich_tournament(final)


class BannerIn(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    subtitle: Optional[str] = ""
    image: str  # URL or base64 data URL
    link: Optional[str] = None
    active: bool = True
    order: int = 0


@api.get("/banners")
async def list_banners():
    docs = await db.banners.find({"active": True}, {"_id": 0}).sort("order", 1).to_list(20)
    return docs


@api.get("/admin/banners")
async def list_all_banners(user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    docs = await db.banners.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    return docs


@api.post("/banners")
async def create_banner(body: BannerIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    b = {"id": str(uuid.uuid4()), **body.model_dump(), "created_at": iso(now_utc())}
    await db.banners.insert_one(b)
    b.pop("_id", None)
    return b


@api.put("/banners/{bid}")
async def update_banner(bid: str, body: BannerIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    await db.banners.update_one({"id": bid}, {"$set": body.model_dump()})
    r = await db.banners.find_one({"id": bid}, {"_id": 0})
    return r


@api.delete("/banners/{bid}")
async def delete_banner(bid: str, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    await db.banners.delete_one({"id": bid})
    return {"ok": True}


# ---------------- META ----------------
@api.get("/games")
async def list_games():
    return GAMES


@api.get("/limits")
async def get_limits():
    return {
        "clan_default": CLAN_LIMIT_DEFAULT,
        "clan_plus": CLAN_LIMIT_PLUS,
        "vice_default": VICE_LIMIT_DEFAULT,
        "vice_plus": VICE_LIMIT_PLUS,
        "bo_total": BO_TOTAL,
        "maps_to_win": MAPS_TO_WIN,
        "points_win": POINTS_WIN,
        "points_loss": POINTS_LOSS,
        "points_withdraw": POINTS_WITHDRAW,
        "video_plus_mb": PLUS_VIDEO_MAX_BYTES // (1024 * 1024),
        "video_free_mb": FREE_VIDEO_MAX_BYTES // (1024 * 1024),
    }


@api.post("/upload/video")
async def upload_video(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload a video file to disk; returns the URL. Limit depends on Plus."""
    max_bytes = PLUS_VIDEO_MAX_BYTES if user_is_plus(user) else FREE_VIDEO_MAX_BYTES
    ext = "mp4"
    if file.filename and "." in file.filename:
        candidate = file.filename.rsplit(".", 1)[-1].lower()
        if candidate in ("mp4", "webm", "mov", "mkv", "avi"):
            ext = candidate
    fname = f"{uuid.uuid4()}.{ext}"
    dest = UPLOAD_DIR / fname
    written = 0
    CHUNK = 1024 * 1024
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    out.close()
                    dest.unlink(missing_ok=True)
                    limit_mb = max_bytes // (1024 * 1024)
                    msg = f"الفيديو كبير. الحد الأقصى {limit_mb}MB"
                    if not user_is_plus(user):
                        msg += " — ترقى لـ Plus للحصول على 500MB"
                    raise HTTPException(400, msg)
                out.write(chunk)
    finally:
        await file.close()
    return {"url": f"/api/uploads/videos/{fname}", "size": written}


@api.get("/")
async def root():
    return {"message": "Rivals Esports API"}


# ---------------- PROFILE / STREAMING URLS ----------------
def _is_url(s: str) -> bool:
    if not s:
        return False
    return s.startswith("http://") or s.startswith("https://")


@api.put("/me/profile")
async def update_my_profile(body: ProfileUpdateIn, user: dict = Depends(get_current_user)):
    """Update Activision ID and streaming URLs for the logged-in user.
    Activision ID can only be changed once per 14 days."""
    update = {}
    if body.act is not None:
        v = body.act.strip()
        if v and len(v) < 2:
            raise HTTPException(400, "Activision ID قصير جدا")
        if v and v != (user.get("act") or ""):
            last_changed = user.get("act_changed_at")
            if last_changed:
                try:
                    last_dt = datetime.fromisoformat(last_changed)
                    next_allowed = last_dt + timedelta(days=ACT_CHANGE_COOLDOWN_DAYS)
                    if now_utc() < next_allowed:
                        days = (next_allowed - now_utc()).days
                        hrs = int((next_allowed - now_utc()).total_seconds() / 3600) % 24
                        raise HTTPException(
                            400,
                            f"لا يمكنك تغيير الـ Activision ID إلا مرة كل أسبوعين. المتبقي: {days} يوم و{hrs} ساعة",
                        )
                except HTTPException:
                    raise
                except Exception:
                    pass
            update["act"] = v
            update["act_changed_at"] = iso(now_utc())
    for field in ("twitch_url", "kick_url", "tiktok_url"):
        val = getattr(body, field)
        if val is None:
            continue
        val = val.strip()
        if val and not _is_url(val):
            raise HTTPException(400, f"رابط {field} غير صالح")
        update[field] = val
    # Personal Plus gated visual customization
    visual_fields = {"avatar": body.avatar, "banner": body.banner, "accent_color": body.accent_color}
    wants_visual = any(v is not None for v in visual_fields.values())
    if wants_visual and not user_is_personal_plus(user):
        raise HTTPException(403, "تخصيص الصورة والبانر واللون متاح لمشتركي Personal Plus فقط")
    AVATAR_MAX = 2_000_000
    BANNER_MAX = 3_000_000
    HEX_RE = "#"
    if body.avatar is not None:
        v = body.avatar.strip()
        if v and (not v.startswith("data:image/")) and (not v.startswith("http")):
            raise HTTPException(400, "صيغة الصورة غير صحيحة")
        if v.startswith("data:") and len(v) > AVATAR_MAX * 1.4:
            raise HTTPException(400, "حجم الصورة كبير (الحد 2MB)")
        update["avatar"] = v or None
    if body.banner is not None:
        v = body.banner.strip()
        if v and (not v.startswith("data:image/")) and (not v.startswith("http")):
            raise HTTPException(400, "صيغة البانر غير صحيحة")
        if v.startswith("data:") and len(v) > BANNER_MAX * 1.4:
            raise HTTPException(400, "حجم البانر كبير (الحد 3MB)")
        update["banner"] = v or None
    if body.accent_color is not None:
        v = body.accent_color.strip()
        if v and (not v.startswith(HEX_RE) or len(v) not in (4, 7)):
            raise HTTPException(400, "اللون يجب أن يكون hex مثل #FFCC00")
        update["accent_color"] = v or None
    if update:
        await db.users.update_one({"id": user["id"]}, {"$set": update})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return sanitize_user(fresh)


# ---------------- LIVE STREAM DETECTION ----------------
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")
_twitch_token_cache: dict = {"token": None, "expires_at": None}


def _extract_handle(url: str, hosts: list[str]) -> Optional[str]:
    if not url:
        return None
    try:
        # naive parse: split by "/" after host
        lower = url.lower()
        for h in hosts:
            if h in lower:
                tail = url.split(h, 1)[1].lstrip("/")
                handle = tail.split("/")[0].split("?")[0].strip()
                return handle or None
        return None
    except Exception:
        return None


async def _get_twitch_token() -> Optional[str]:
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return None
    cached = _twitch_token_cache.get("token")
    exp = _twitch_token_cache.get("expires_at")
    if cached and exp and now_utc() < exp:
        return cached
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id": TWITCH_CLIENT_ID,
                    "client_secret": TWITCH_CLIENT_SECRET,
                    "grant_type": "client_credentials",
                },
            )
            if r.status_code != 200:
                return None
            data = r.json()
            _twitch_token_cache["token"] = data.get("access_token")
            ttl = int(data.get("expires_in", 3600))
            _twitch_token_cache["expires_at"] = now_utc() + timedelta(seconds=max(60, ttl - 60))
            return _twitch_token_cache["token"]
    except Exception as exc:
        logger.warning(f"Twitch token error: {exc}")
        return None


async def _twitch_live_info(handle: str) -> Optional[dict]:
    token = await _get_twitch_token()
    if not token:
        return None
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                "https://api.twitch.tv/helix/streams",
                params={"user_login": handle},
                headers={"Client-Id": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"},
            )
            if r.status_code != 200:
                return None
            data = r.json().get("data") or []
            if not data:
                return None
            s = data[0]
            thumb = s.get("thumbnail_url", "").replace("{width}", "320").replace("{height}", "180")
            return {
                "platform": "twitch",
                "live": True,
                "title": s.get("title", ""),
                "viewer_count": s.get("viewer_count", 0),
                "thumbnail": thumb,
                "url": f"https://twitch.tv/{handle}",
            }
    except Exception as exc:
        logger.warning(f"Twitch live check error: {exc}")
        return None


async def _kick_live_info(handle: str) -> Optional[dict]:
    """Best-effort Kick.com live check via public unofficial endpoint."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5, headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get(f"https://kick.com/api/v2/channels/{handle}")
            if r.status_code != 200:
                return None
            data = r.json()
            ls = data.get("livestream")
            if not ls or not ls.get("is_live"):
                return None
            return {
                "platform": "kick",
                "live": True,
                "title": ls.get("session_title", ""),
                "viewer_count": ls.get("viewer_count", 0),
                "thumbnail": (ls.get("thumbnail") or {}).get("url", ""),
                "url": f"https://kick.com/{handle}",
            }
    except Exception as exc:
        logger.warning(f"Kick live check error: {exc}")
        return None


@api.get("/users/{user_id}/live")
async def user_live(user_id: str):
    """Returns active live streams for a given user across linked platforms."""
    u = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        raise HTTPException(404, "غير موجود")
    result = {"twitch": None, "kick": None, "tiktok": None}
    th = _extract_handle(u.get("twitch_url", ""), ["twitch.tv/"])
    kh = _extract_handle(u.get("kick_url", ""), ["kick.com/"])
    if th:
        result["twitch"] = await _twitch_live_info(th)
    if kh:
        result["kick"] = await _kick_live_info(kh)
    # TikTok: link only — no live detection
    if u.get("tiktok_url"):
        result["tiktok"] = {"platform": "tiktok", "live": False, "url": u["tiktok_url"]}
    return result


@api.get("/matches/{match_id}/live-streams")
async def match_live_streams(match_id: str, user: dict = Depends(get_current_user)):
    """Returns active live streams for any leader/vice/member of the two clans in this match.
    Used by the chat sidebar."""
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "غير موجود")
    a = await db.clans.find_one({"id": m["clan_a_id"]}, {"_id": 0})
    b = await db.clans.find_one({"id": m["clan_b_id"]}, {"_id": 0})
    if not a or not b:
        return []
    member_ids = list(set(a.get("member_ids", []) + b.get("member_ids", [])))
    docs = await db.users.find(
        {"id": {"$in": member_ids},
         "$or": [{"twitch_url": {"$ne": ""}}, {"kick_url": {"$ne": ""}}]},
        {"_id": 0},
    ).to_list(200)
    streams = []
    for u in docs:
        live_data = await user_live(u["id"])
        for k in ("twitch", "kick"):
            v = live_data.get(k)
            if v and v.get("live"):
                streams.append({
                    "user_id": u["id"],
                    "username": u["username"],
                    "clan_id": u.get("clan_id"),
                    **v,
                })
    return streams


# ---------------- CLAN ARCHIVE ----------------
@api.post("/clans/{clan_id}/archive")
async def archive_clan(clan_id: str, user: dict = Depends(get_current_user)):
    """Leader (or staff) turns the clan OFF: kicks all members, deactivates clan."""
    clan = await _get_clan(clan_id)
    if user["id"] != clan["leader_id"] and not is_staff(user):
        raise HTTPException(403, "فقط القائد أو المنظم")
    if clan.get("archived"):
        raise HTTPException(400, "الكلان مؤرشف بالفعل")
    member_ids = clan.get("member_ids", [])
    cooldown_until = iso(now_utc() + timedelta(hours=CLAN_LEAVE_COOLDOWN_HOURS))
    if member_ids:
        await db.users.update_many(
            {"id": {"$in": member_ids}},
            {"$set": {"clan_id": None, "clan_cooldown_until": cooldown_until}},
        )
    await db.clans.update_one(
        {"id": clan_id},
        {"$set": {
            "archived": True,
            "archived_at": iso(now_utc()),
            "member_ids": [],
            "vice_leader_ids": [],
        }},
    )
    return {"ok": True, "kicked": len(member_ids)}


@api.post("/clans/{clan_id}/restore")
async def restore_clan(clan_id: str, user: dict = Depends(get_current_user)):
    """Leader (or staff) restores a previously archived clan. Members stay kicked
    (they were removed at archive time). Leader rejoins automatically."""
    clan = await db.clans.find_one({"id": clan_id}, {"_id": 0})
    if not clan:
        raise HTTPException(404, "الكلان غير موجود")
    if user["id"] != clan["leader_id"] and not is_staff(user):
        raise HTTPException(403, "فقط القائد الأصلي أو المنظم")
    if not clan.get("archived"):
        raise HTTPException(400, "الكلان غير مؤرشف")
    # If leader is in another clan now, block
    leader_doc = await db.users.find_one({"id": clan["leader_id"]})
    if leader_doc and leader_doc.get("clan_id") and leader_doc["clan_id"] != clan_id:
        raise HTTPException(400, "القائد الأصلي في كلان آخر — اطلب منه المغادرة أولاً")
    await db.clans.update_one(
        {"id": clan_id},
        {"$set": {
            "archived": False,
            "restored_at": iso(now_utc()),
            "member_ids": [clan["leader_id"]],
            "vice_leader_ids": [],
        }},
    )
    # Bring leader back, clear any cooldown
    await db.users.update_one(
        {"id": clan["leader_id"]},
        {"$set": {"clan_id": clan_id, "clan_cooldown_until": None}},
    )
    return {"ok": True, "clan_id": clan_id}


@api.get("/me/archived-clan")
async def my_archived_clan(user: dict = Depends(get_current_user)):
    """Returns the most recent archived clan still led by the user (so they can restore it)."""
    doc = await db.clans.find_one(
        {"leader_id": user["id"], "archived": True},
        {"_id": 0},
        sort=[("archived_at", -1)],
    )
    return doc or None


@api.post("/admin/clans/{clan_id}/transfer/{member_id}")
async def admin_transfer_clan_ownership(clan_id: str, member_id: str, user: dict = Depends(get_current_user)):
    """Owner/Admin transfers clan leadership to a member of that clan."""
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    clan = await _get_clan(clan_id)
    if member_id == clan["leader_id"]:
        raise HTTPException(400, "هذا اللاعب هو القائد بالفعل")
    if member_id not in clan.get("member_ids", []):
        raise HTTPException(400, "اللاعب ليس عضواً في الكلان")
    target = await db.users.find_one({"id": member_id})
    if not target:
        raise HTTPException(404, "اللاعب غير موجود")
    old_leader = clan["leader_id"]
    # Old leader becomes a regular member (still in the clan); remove from vice list if present
    await db.clans.update_one(
        {"id": clan_id},
        {
            "$set": {"leader_id": member_id},
            "$pull": {"vice_leader_ids": member_id},
        },
    )
    return {"ok": True, "new_leader_id": member_id, "old_leader_id": old_leader}


@api.get("/online-clans")
async def list_online_clans(q: str = ""):
    """Clans with at least one currently-online member (last_seen_at within ONLINE_WINDOW)."""
    cutoff = iso(now_utc() - timedelta(minutes=ONLINE_WINDOW_MINUTES))
    online_users = await db.users.find(
        {"clan_id": {"$ne": None}, "last_seen_at": {"$gte": cutoff}},
        {"_id": 0, "clan_id": 1},
    ).to_list(1000)
    clan_ids = list({u["clan_id"] for u in online_users if u.get("clan_id")})
    if not clan_ids:
        return []
    query = {"id": {"$in": clan_ids}, "archived": {"$ne": True}}
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"tag": {"$regex": q, "$options": "i"}},
        ]
    clans = await db.clans.find(query, {"_id": 0}).sort("points", -1).to_list(200)
    return clans


# ---------------- MATCH-LEVEL PRAYER BREAK (15-min chat-side pause) ----------------
@api.post("/matches/{match_id}/match-prayer-break")
async def start_match_prayer_break(match_id: str, user: dict = Depends(get_current_user)):
    """A clan leader/vice starts a 15-min full-match prayer break.
    All gameplay actions (votes, grace claims) are paused for the duration."""
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    side = _user_side(user, a, b)
    if not side and not is_staff(user):
        raise HTTPException(403, "للقادة والنواب فقط")
    existing = match.get("match_prayer_break")
    if existing and existing.get("ends_at"):
        try:
            ends = datetime.fromisoformat(existing["ends_at"])
            if now_utc() < ends:
                raise HTTPException(400, "بريك صلاة جارٍ بالفعل")
        except HTTPException:
            raise
        except Exception:
            pass
    # Per-user 30-min anti-spam cooldown on prayer-break trigger
    cd_iso = user.get("prayer_break_cooldown_until")
    if cd_iso and not is_staff(user):
        try:
            cd_dt = datetime.fromisoformat(cd_iso)
            if now_utc() < cd_dt:
                mins = int((cd_dt - now_utc()).total_seconds() / 60) + 1
                raise HTTPException(400, f"يجب الانتظار {mins} دقيقة قبل بريك جديد")
        except HTTPException:
            raise
        except Exception:
            pass
    now = now_utc()
    pb = {
        "started_at": iso(now),
        "ends_at": iso(now + timedelta(seconds=MATCH_PRAYER_BREAK_SECONDS)),
        "started_by_clan": side or "ADMIN",
        "started_by_user_id": user["id"],
        "started_by_username": user["username"],
        "resumed": False,
    }
    await db.matches.update_one({"id": match_id}, {"$set": {"match_prayer_break": pb}})
    # Set per-user cooldown so the same user can't spam another prayer break for 30 min
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"prayer_break_cooldown_until": iso(now + timedelta(minutes=PRAYER_BREAK_USER_COOLDOWN_MIN))}},
    )
    # System chat message
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "user_id": "system",
        "username": "النظام",
        "user_role": "admin",
        "user_clan_id": None,
        "type": "text",
        "text": f"🕌 بدأ بريك الصلاة (15 دقيقة) — توقف اللعب — بدأها كلان {side or 'إدارة'}",
        "image": None, "video": None,
        "opponent_decision": None, "admin_decision": None, "admin_note": "",
        "created_at": iso(now_utc()),
    })
    return pb


@api.post("/matches/{match_id}/match-prayer-resume")
async def resume_match_prayer_break(match_id: str, user: dict = Depends(get_current_user)):
    """The team that requested the prayer break (or staff) ends it early."""
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    pb = match.get("match_prayer_break")
    if not pb:
        raise HTTPException(400, "لا يوجد بريك صلاة جارٍ")
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    side = _user_side(user, a, b)
    if not is_staff(user) and pb.get("started_by_clan") != side:
        raise HTTPException(403, "فقط الفريق الذي بدأ البريك يمكنه إنهاؤه")
    pb["resumed"] = True
    pb["resumed_at"] = iso(now_utc())
    pb["ends_at"] = iso(now_utc())
    await db.matches.update_one({"id": match_id}, {"$set": {"match_prayer_break": pb}})
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "user_id": "system",
        "username": "النظام",
        "user_role": "admin",
        "user_clan_id": None,
        "type": "text",
        "text": "▶️ تم إنهاء بريك الصلاة — استئناف المباراة",
        "image": None, "video": None,
        "opponent_decision": None, "admin_decision": None, "admin_note": "",
        "created_at": iso(now_utc()),
    })
    return pb


# ---------------- ADMIN: edit users / clans, forgot-password ----------------
@api.put("/admin/users/{user_id}")
async def admin_edit_user(user_id: str, body: AdminUserEditIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "المستخدم غير موجود")
    if target.get("role") == "owner" and not is_owner(user):
        raise HTTPException(403, "لا يمكن تعديل المالك")
    update = {}
    if body.username is not None:
        v = body.username.strip()
        if len(v) < 2:
            raise HTTPException(400, "اسم المستخدم قصير")
        clash = await db.users.find_one({"username": v, "id": {"$ne": user_id}})
        if clash:
            raise HTTPException(400, "الاسم محجوز")
        update["username"] = v
    if body.email is not None:
        v = body.email.lower()
        clash = await db.users.find_one({"email": v, "id": {"$ne": user_id}})
        if clash:
            raise HTTPException(400, "البريد مستخدم")
        update["email"] = v
    if body.password is not None:
        update["password_hash"] = hash_pw(body.password)
    if body.act is not None:
        update["act"] = body.act.strip()
    if update:
        await db.users.update_one({"id": user_id}, {"$set": update})
    fresh = await db.users.find_one({"id": user_id}, {"_id": 0})
    return sanitize_user(fresh)


@api.put("/admin/clans/{clan_id}")
async def admin_edit_clan(clan_id: str, body: AdminClanEditIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    await _get_clan(clan_id)  # 404 if missing
    update = {}
    if body.name is not None:
        clash = await db.clans.find_one({"name": body.name, "id": {"$ne": clan_id}})
        if clash:
            raise HTTPException(400, "الاسم مستخدم")
        update["name"] = body.name
    if body.tag is not None:
        clash = await db.clans.find_one({"tag": body.tag, "id": {"$ne": clan_id}})
        if clash:
            raise HTTPException(400, "التاج مستخدم")
        update["tag"] = body.tag
    if body.description is not None:
        update["description"] = body.description
    if update:
        await db.clans.update_one({"id": clan_id}, {"$set": update})
    fresh = await db.clans.find_one({"id": clan_id}, {"_id": 0})
    return fresh


@api.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordIn):
    """MOCKED: Generates a reset link and stores it as a pending reset request.
    Owner/Admins can view all pending requests in the dashboard.
    NOTE: email delivery is NOT yet wired (waiting for SMTP/Resend API key)."""
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    # Always return 200 so as not to leak account existence
    if user:
        token = uuid.uuid4().hex
        await db.password_resets.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "email": email,
            "username": user["username"],
            "token": token,
            "status": "pending",
            "created_at": iso(now_utc()),
            "expires_at": iso(now_utc() + timedelta(hours=24)),
        })
        logger.info(f"[FORGOT-PASSWORD MOCK] user={email} token={token}")
    return {"ok": True, "message": "إن وُجد الحساب، سيتلقى الإدارة الطلب لإرسال الرابط"}


@api.get("/admin/password-resets")
async def admin_list_resets(user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    docs = await db.password_resets.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs


@api.post("/admin/password-resets/{rid}/complete")
async def admin_complete_reset(rid: str, user: dict = Depends(get_current_user)):
    """Mark a reset request as 'sent/completed' once admin emails the user the link manually."""
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    await db.password_resets.update_one(
        {"id": rid}, {"$set": {"status": "completed", "completed_at": iso(now_utc())}}
    )
    return {"ok": True}


# ---------------- BLACKLIST (cheaters log) ----------------
@api.get("/blacklist")
async def list_blacklist():
    """PUBLIC list of blacklisted cheaters — anyone can view, only staff can mutate."""
    docs = await db.blacklist.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@api.post("/blacklist")
async def add_blacklist(body: BlacklistIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    target_account = None
    if body.player_user_id:
        u = await db.users.find_one({"id": body.player_user_id}, {"_id": 0})
        if u:
            target_account = sanitize_user(u)
    entry = {
        "id": str(uuid.uuid4()),
        "player_name": body.player_name,
        "player_user_id": body.player_user_id,
        "player_email": body.player_email or (target_account or {}).get("email", ""),
        "player_account": target_account,
        "cheat_tool": body.cheat_tool,
        "details": body.details or "",
        "proof_image": body.proof_image or "",
        "added_by": user["id"],
        "added_by_username": user["username"],
        "created_at": iso(now_utc()),
    }
    await db.blacklist.insert_one(entry)
    entry.pop("_id", None)
    return entry


@api.delete("/blacklist/{bid}")
async def remove_blacklist(bid: str, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    await db.blacklist.delete_one({"id": bid})
    return {"ok": True}


# ---------------- MONTHLY LEAGUE (auto reset + trophy) ----------------
_ARABIC_MONTHS = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]


def _current_league_key() -> str:
    n = now_utc()
    return f"{n.year}-{n.month:02d}"


def _current_league_name() -> str:
    n = now_utc()
    return f"دوري رايفلز - {_ARABIC_MONTHS[n.month - 1]}"


async def _ensure_current_league() -> dict:
    """Returns the active league doc; creates it if missing. Closes previous month and grants
    a trophy to the top-points clan."""
    key = _current_league_key()
    current = await db.leagues.find_one({"key": key}, {"_id": 0})
    if current:
        return current
    # Close previous active league(s)
    prev_cursor = db.leagues.find({"status": "active"}, {"_id": 0})
    async for prev in prev_cursor:
        # Champion = highest points clan at moment of close
        top = await db.clans.find_one(
            {"archived": {"$ne": True}}, {"_id": 0}, sort=[("points", -1)]
        )
        update_fields = {"status": "finished", "finished_at": iso(now_utc())}
        if top:
            update_fields["champion_clan_id"] = top["id"]
            update_fields["champion_clan_name"] = top["name"]
            await db.clans.update_one(
                {"id": top["id"]},
                {"$push": {"trophies": {
                    "id": str(uuid.uuid4()),
                    "kind": "league",
                    "label": f"بطل {prev['name']}",
                    "league_key": prev["key"],
                    "awarded_at": iso(now_utc()),
                }}}
            )
        await db.leagues.update_one({"key": prev["key"]}, {"$set": update_fields})
        # Reset all clan points/wins/losses for the new league
        await db.clans.update_many({}, {"$set": {"points": 0, "wins": 0, "losses": 0}})
        await db.users.update_many({"role": {"$ne": "owner"}}, {"$set": {"points": 0}})
    new_league = {
        "id": str(uuid.uuid4()),
        "key": key,
        "name": _current_league_name(),
        "status": "active",
        "started_at": iso(now_utc()),
        "finished_at": None,
        "champion_clan_id": None,
        "champion_clan_name": None,
    }
    await db.leagues.insert_one(new_league)
    new_league.pop("_id", None)
    logger.info(f"League created/rotated: {new_league['name']}")
    return new_league


@api.get("/leagues/current")
async def current_league():
    return await _ensure_current_league()


@api.get("/leagues")
async def list_leagues():
    docs = await db.leagues.find({}, {"_id": 0}).sort("started_at", -1).to_list(50)
    return docs


async def _league_rotation_loop() -> None:
    """Background task: checks every hour if a new month has started and rotates the league."""
    while True:
        try:
            await _ensure_current_league()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"League rotation error: {exc}")
        await asyncio.sleep(3600)


app.include_router(api)

# Serve uploaded videos via /api/uploads/videos/*
app.mount("/api/uploads/videos", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
