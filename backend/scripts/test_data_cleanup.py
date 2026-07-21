#!/usr/bin/env python3
"""Cleanup pytest/smoke data from MongoDB while preserving real production records."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)

MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME", "rivals")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI/MONGODB_URI is required")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# ---- test patterns ----
USER_EMAIL_RE = re.compile(r"(^((test|lb|ls|pytest|smoke)[^@]*)@)|(@example\.com$)", re.I)
USER_USERNAME_RE = re.compile(r"^(tu_|lb_|ls_|py_|smoke)", re.I)
USER_ID_RE = re.compile(r"^(test_|smoke2_)", re.I)

CLAN_NAME_RE = re.compile(
    r"^(TEST_|MPBA_|MPBB_|MP2A_|MP2B_|ArchClan_|S2A_|S2B_|TEST_LS_|Renamed_)",
    re.I,
)
LEAGUE_NAME_RE = re.compile(r"^(League_(DataURL|Edit|LB|WD|AI)_|Edited_)", re.I)

SAFE_KEEP_EMAILS = {
    "owner@rivalsesports.games",
    "admin@rivals.gg",
}


def is_test_user(u: dict[str, Any]) -> bool:
    email = str(u.get("email") or "").strip().lower()
    username = str(u.get("username") or "").strip().lower()
    uid = str(u.get("id") or "").strip()

    if email in SAFE_KEEP_EMAILS:
        return False

    if USER_ID_RE.search(uid):
        return True
    if USER_EMAIL_RE.search(email):
        return True
    if USER_USERNAME_RE.search(username):
        return True

    # helper-generated temp admin rows from tests
    if email == "" and uid.startswith("test_"):
        return True

    return False


def main() -> None:
    users = list(db.users.find({}, {"_id": 0}))
    test_users = [u for u in users if is_test_user(u)]
    test_user_ids = {u["id"] for u in test_users if u.get("id")}

    clans = list(db.clans.find({}, {"_id": 0}))
    test_clan_ids: set[str] = set()
    for c in clans:
        cid = str(c.get("id") or "")
        if not cid:
            continue
        leader_id = str(c.get("leader_id") or "")
        member_ids = {str(x) for x in (c.get("member_ids") or [])}
        name = str(c.get("name") or "")
        if leader_id in test_user_ids or (member_ids & test_user_ids) or CLAN_NAME_RE.search(name):
            test_clan_ids.add(cid)

    matches = list(
        db.matches.find(
            {
                "$or": [
                    {"clan_a_id": {"$in": list(test_clan_ids)}},
                    {"clan_b_id": {"$in": list(test_clan_ids)}},
                ]
            },
            {"_id": 0, "id": 1},
        )
    )
    test_match_ids = {m.get("id") for m in matches if m.get("id")}

    challenges = list(
        db.challenges.find(
            {
                "$or": [
                    {"clan_id": {"$in": list(test_clan_ids)}},
                    {"opponent_clan_id": {"$in": list(test_clan_ids)}},
                ]
            },
            {"_id": 0, "id": 1},
        )
    )
    test_challenge_ids = {c.get("id") for c in challenges if c.get("id")}

    league_ids = {
        d.get("id")
        for d in db.leagues.find({"name": {"$regex": LEAGUE_NAME_RE.pattern, "$options": "i"}}, {"_id": 0, "id": 1})
        if d.get("id")
    }

    report: dict[str, int] = {}

    def _del(col: str, query: dict[str, Any], label: str | None = None) -> None:
        deleted = db[col].delete_many(query).deleted_count
        report[label or col] = report.get(label or col, 0) + int(deleted)

    # child collections first
    if test_user_ids:
        _del("auth_sessions", {"user_id": {"$in": list(test_user_ids)}})
        _del("email_otps", {"user_id": {"$in": list(test_user_ids)}})
        _del("notifications", {"$or": [{"user_id": {"$in": list(test_user_ids)}}, {"sender_id": {"$in": list(test_user_ids)}}]})
        _del("invites", {"$or": [{"user_id": {"$in": list(test_user_ids)}}, {"from_user_id": {"$in": list(test_user_ids)}}]})
        _del("join_requests", {"user_id": {"$in": list(test_user_ids)}})
        _del("blacklist", {"$or": [{"created_by": {"$in": list(test_user_ids)}}, {"user_id": {"$in": list(test_user_ids)}}]})
        _del("discord_levels", {"user_id": {"$in": list(test_user_ids)}})
        _del("guard_sessions", {"user_id": {"$in": list(test_user_ids)}})

    if test_clan_ids:
        _del("join_requests", {"clan_id": {"$in": list(test_clan_ids)}})
        _del("invites", {"clan_id": {"$in": list(test_clan_ids)}})
        _del("challenges", {"$or": [{"clan_id": {"$in": list(test_clan_ids)}}, {"opponent_clan_id": {"$in": list(test_clan_ids)}}]})
        _del("discord_clan_roles", {"clan_id": {"$in": list(test_clan_ids)}})
        _del("discord_plus_channels", {"clan_id": {"$in": list(test_clan_ids)}})

    if test_match_ids:
        _del("chat_messages", {"match_id": {"$in": list(test_match_ids)}})
        _del("guard_sessions", {"match_id": {"$in": list(test_match_ids)}})
        _del("matches", {"id": {"$in": list(test_match_ids)}})

    if test_challenge_ids:
        _del("notifications", {"related_id": {"$in": list(test_challenge_ids)}})

    if test_clan_ids:
        _del("clans", {"id": {"$in": list(test_clan_ids)}})

    if test_user_ids:
        _del("users", {"id": {"$in": list(test_user_ids)}})

    if league_ids:
        _del("leagues", {"id": {"$in": list(league_ids)}})
        _del("league_standings", {"league_id": {"$in": list(league_ids)}})

    print(f"Database: {DB_NAME}")
    print(f"Detected test users: {len(test_user_ids)}")
    print(f"Detected test clans: {len(test_clan_ids)}")
    print(f"Detected test matches: {len(test_match_ids)}")
    print(f"Detected test challenges: {len(test_challenge_ids)}")
    print(f"Detected test leagues: {len(league_ids)}")
    print("---- Deletions ----")
    for k in sorted(report):
        print(f"{k}: {report[k]}")


if __name__ == "__main__":
    try:
        main()
    finally:
        client.close()
