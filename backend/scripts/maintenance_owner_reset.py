import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)
load_dotenv(ROOT_DIR.parent / ".env", override=False)

EMAIL = "prev@rivals.gg"
TEMP_PASSWORD = "RivalsAdmin2026!"
FORCE_ROLE = "owner"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def main() -> None:
    mongo_url = (
        os.environ.get("MONGO_URI")
        or os.environ.get("MONGO_URL")
        or "mongodb://localhost:27017"
    )
    db_name = os.environ.get("DB_NAME", "rivals")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    email = EMAIL.strip().lower()
    existing = await db.users.find_one({"email": email}, {"_id": 0})

    base_set = {
        "email": email,
        "password_hash": hash_pw(TEMP_PASSWORD),
        "role": FORCE_ROLE,
        "status": "Active",
        "updated_at": iso(now_utc()),
    }

    if existing:
        username = (existing.get("username") or "PrevOwner").strip() or "PrevOwner"
        update_doc = {
            "$set": {
                **base_set,
                "username": username,
                "is_admin": True,
                "admin": True,
                "is_owner": True,
            },
            "$unset": {
                "banned_until": "",
                "banned_at": "",
                "ban_reason": "",
            },
        }
        await db.users.update_one({"id": existing["id"]}, update_doc)
        user_id = existing["id"]
        action = "updated"
    else:
        user_id = str(uuid.uuid4())
        username = "PrevOwner"
        doc = {
            "id": user_id,
            "email": email,
            "username": username,
            "act": "owner#0001",
            "password_hash": base_set["password_hash"],
            "role": FORCE_ROLE,
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
            "is_plus": True,
            "personal_plus_until": iso(now_utc() + timedelta(days=3650)),
            "plus_expires_at": iso(now_utc() + timedelta(days=3650)),
            "clan_cooldown_until": None,
            "status": "Active",
            "is_admin": True,
            "admin": True,
            "is_owner": True,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        }
        await db.users.insert_one(doc)
        action = "created"

    fresh = await db.users.find_one({"id": user_id}, {"_id": 0, "id": 1, "email": 1, "username": 1, "role": 1, "status": 1})

    print("maintenance_result=ok")
    print(f"action={action}")
    print(f"user_id={fresh.get('id')}")
    print(f"email={fresh.get('email')}")
    print(f"username={fresh.get('username')}")
    print(f"role={fresh.get('role')}")
    print(f"status={fresh.get('status')}")
    print(f"temp_password={TEMP_PASSWORD}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
