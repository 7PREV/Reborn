from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
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


def sanitize_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "username": u["username"],
        "role": u.get("role", "player"),
        "clan_id": u.get("clan_id"),
        "points": u.get("points", 0),
        "avatar": u.get("avatar"),
        "is_plus": user_is_plus(u),
        "plus_expires_at": u.get("plus_expires_at"),
        "created_at": u.get("created_at"),
    }


async def _maybe_grant_full_clan_reward(clan_id: str) -> bool:
    """When a clan first reaches 7 members, grant the leader 7-day Plus.
    Returns True if reward was just granted."""
    clan = await db.clans.find_one({"id": clan_id})
    if not clan:
        return False
    if clan.get("founder_reward_given"):
        return False
    if len(clan.get("member_ids", [])) < CLAN_LIMIT_DEFAULT:
        return False
    leader = await db.users.find_one({"id": clan["leader_id"]})
    if not leader:
        return False
    # Only grant if leader is not already on permanent Plus
    if not leader.get("is_plus"):
        new_expiry = now_utc() + timedelta(days=7)
        existing_exp = leader.get("plus_expires_at")
        # Extend if already has a future expiry
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


# ---------------- Startup ----------------
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
        "password_hash": hash_pw(body.password),
        "role": "player",
        "points": 0,
        "clan_id": None,
        "avatar": None,
        "is_plus": False,
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
    query = {}
    if q:
        query = {"$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"tag": {"$regex": q, "$options": "i"}},
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
            await db.users.update_one({"id": req["user_id"]}, {"$set": {"clan_id": clan_id}})
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
        clan = await _get_clan(inv["clan_id"])
        max_members, _ = await _leader_limits(clan)
        if len(clan.get("member_ids", [])) >= max_members:
            raise HTTPException(400, "الكلان ممتلئ")
        await db.users.update_one({"id": user["id"]}, {"$set": {"clan_id": inv["clan_id"]}})
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
    await db.users.update_one({"id": member_id}, {"$set": {"clan_id": None}})
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
    await db.users.update_one({"id": user["id"]}, {"$set": {"clan_id": None}})
    return {"ok": True}


# ---------------- MATCHES ----------------
async def _enrich_match(m: dict) -> dict:
    a = await db.clans.find_one({"id": m["clan_a_id"]}, {"_id": 0, "name": 1, "tag": 1, "id": 1})
    b = await db.clans.find_one({"id": m["clan_b_id"]}, {"_id": 0, "name": 1, "tag": 1, "id": 1})
    m["clan_a"] = a
    m["clan_b"] = b
    return m


def _count_maps(maps: list) -> tuple[int, int]:
    return (
        sum(1 for mp in maps if mp.get("winner") and mp["winner"] == "A"),
        sum(1 for mp in maps if mp.get("winner") and mp["winner"] == "B"),
    )


POINTS_WIN = 3
POINTS_LOSS = -1
POINTS_WITHDRAW = -3

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
    maps = [
        {"index": i, "vote_a": None, "vote_b": None, "winner": None, "disputed": False, "admin_resolved": False}
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


@api.post("/matches/{match_id}/vote-map")
async def vote_map(match_id: str, body: MapVoteIn, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")
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
        {}, {"_id": 0, "id": 1, "name": 1, "tag": 1, "points": 1, "wins": 1, "losses": 1}
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
             "disputed": False, "admin_resolved": False}
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
    }


@api.get("/")
async def root():
    return {"message": "Rivals Esports API"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
