import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)

MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI") or "mongodb://localhost:27017"
DB_NAME = os.environ.get("DB_NAME", "rivals")
JWT_SECRET = os.environ.get("JWT_SECRET", "test-secret")
JWT_ALG = os.environ.get("JWT_ALG", "HS256")

_mongo = MongoClient(MONGO_URI)
db = _mongo[DB_NAME]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def random_forwarded_for() -> str:
    return f"127.{(uuid.uuid4().int >> 16) % 255}.{(uuid.uuid4().int >> 8) % 255}.{uuid.uuid4().int % 255}"


def test_headers(extra: dict | None = None) -> dict:
    h = {"X-Forwarded-For": random_forwarded_for()}
    if extra:
        h.update(extra)
    return h


def _base_user_doc(email: str, username: str, role: str, act: str) -> dict:
    now = now_utc()
    return {
        "id": f"test_{uuid.uuid4().hex}",
        "email": email.lower(),
        "username": username,
        "act": act,
        "gaming_platform": "ps5",
        "password_hash": "test_hash_not_used",
        "referral_code": f"RF{uuid.uuid4().hex[:8].upper()}",
        "riv_points": 0,
        "premium_until": None,
        "role": role,
        "points": 0,
        "wins": 0,
        "losses": 0,
        "attendances": 0,
        "mvp_count": 0,
        "clan_id": None,
        "clan_joined_at": None,
        "last_clan_id": None,
        "last_clan_joined_at": None,
        "last_clan_left_at": None,
        "avatar": None,
        "banner": None,
        "accent_color": None,
        "avatar_creator": None,
        "is_plus": False,
        "personal_plus_until": (now + timedelta(days=3)).isoformat(),
        "clan_cooldown_until": None,
        "email_verified_at": now.isoformat(),
        "registration_ip": "127.0.0.1",
        "registration_city": "",
        "registration_region": "",
        "registration_country": "",
        "discord_username": "",
        "created_at": now.isoformat(),
    }


def _issue_session_and_token(user_doc: dict) -> tuple[str, str]:
    now = now_utc()
    sid = f"sess_{uuid.uuid4().hex}"
    db.auth_sessions.insert_one(
        {
            "id": sid,
            "user_id": user_doc["id"],
            "created_at": now.isoformat(),
            "last_seen_at": now.isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "revoked_at": None,
            "revoked_reason": None,
            "ip": "127.0.0.1",
            "ua": "pytest",
        }
    )
    token = jwt.encode(
        {
            "sub": user_doc["id"],
            "email": user_doc["email"],
            "role": user_doc["role"],
            "type": "access",
            "sid": sid,
            "exp": now + timedelta(days=2),
        },
        JWT_SECRET,
        algorithm=JWT_ALG,
    )
    return sid, token


def create_user_and_token(role: str = "player", email: str | None = None, username: str | None = None, act: str | None = None) -> tuple[dict, str]:
    suffix = uuid.uuid4().hex[:8]
    email = email or f"pytest_{role}_{suffix}@example.com"
    username = username or f"py_{role}_{suffix}"
    act = act or f"ACT_{suffix}"

    user_doc = _base_user_doc(email=email, username=username, role=role, act=act)
    db.users.insert_one(user_doc)
    _sid, token = _issue_session_and_token(user_doc)
    return user_doc, token


def ensure_admin_token(admin_email: str = "admin@rivals.gg") -> tuple[dict, str]:
    user = db.users.find_one({"email": admin_email.lower()}, {"_id": 0})
    if not user:
        user = _base_user_doc(email=admin_email.lower(), username="Admin", role="admin", act="ADMIN_ACT")
        db.users.insert_one(user)
    else:
        if user.get("role") != "admin":
            db.users.update_one({"id": user["id"]}, {"$set": {"role": "admin"}})
            user["role"] = "admin"
    _sid, token = _issue_session_and_token(user)
    return user, token


def count_pending_reset_otps(user_id: str) -> int:
    return db.email_otps.count_documents({"purpose": "reset_password", "user_id": user_id, "status": "pending"})
