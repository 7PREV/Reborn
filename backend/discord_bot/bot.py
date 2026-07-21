import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List

import discord
from discord import app_commands
from dotenv import load_dotenv
from discord.ext import commands, tasks
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument

ROOT_DIR = Path(__file__).resolve().parent
# Force backend/.env values to override stale PM2 env values (e.g. channel IDs)
load_dotenv(ROOT_DIR.parent / ".env", override=True)
load_dotenv(ROOT_DIR.parent.parent / ".env", override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rivals-discord-bot")


def _env_int(name: str, default: int = 0) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        logger.warning("Invalid integer env %s=%r; using default=%s", name, raw, default)
        return default


def _env_json_object(name: str, default: Optional[dict] = None) -> dict:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default or {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    logger.warning("Invalid JSON env %s; using default object", name)
    return default or {}


def _env_int_set(name: str, default: Optional[set[int]] = None) -> set[int]:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return set(default or set())
    out: set[int] = set()
    for p in raw.split(","):
        part = (p or "").strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except Exception:
            logger.warning("Invalid %s role id value: %r", name, part)
    return out or set(default or set())

MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
DB_NAME = os.environ.get("DB_NAME", "rivals")
DISCORD_BOT_TOKEN = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
DISCORD_GUILD_ID = _env_int("DISCORD_GUILD_ID", 0)
WELCOME_CHANNEL_ID = _env_int("DISCORD_WELCOME_CHANNEL_ID", 0)
SUPPORT_ROLE_ID = _env_int("DISCORD_SUPPORT_ROLE_ID", 0)
PLUS_ROLE_ID = _env_int("DISCORD_PLUS_ROLE_ID", _env_int("DISCORD_RIVALS_PLUS_ROLE_ID", 0))
NEWS_CHANNEL_ID = _env_int("DISCORD_NEWS_CHANNEL_ID", 1522275731982520391)
RANK_CHANNEL_ID = _env_int("DISCORD_RANK_CHANNEL_ID", 1472192794192777330)
LEVEL_UP_CHANNEL_ID = _env_int("LEVEL_UP_CHANNEL_ID", 0)
NEWS_BACKLOG_HOURS = _env_int("DISCORD_NEWS_BACKLOG_HOURS", 168)
TICKET_CATEGORY_ID = _env_int("DISCORD_TICKET_CATEGORY_ID", 0)
TICKET_PANEL_BANNER_GIF_URL = (
    os.environ.get("DISCORD_TICKET_PANEL_BANNER_GIF_URL")
    or "https://cdn.discordapp.com/attachments/1506099199937351812/1522391148822266087/07AD0530-2F43-4ACD-B85D-68A655F2FE3B.png?ex=6a484cbe&is=6a46fb3e&hm=4e3985cbb83944e2880728a0c9f6b684beea396a2f8ac5d4efd8da903391cba0&"
).strip()
TICKET_WELCOME_BANNER_URL = (
    "https://cdn.discordapp.com/attachments/1506099199937351812/1522391148822266087/07AD0530-2F43-4ACD-B85D-68A655F2FE3B.png?ex=6a484cbe&is=6a46fb3e&hm=4e3985cbb83944e2880728a0c9f6b684beea396a2f8ac5d4efd8da903391cba0&"
)
WELCOME_BANNER_URL = (
    os.environ.get("DISCORD_WELCOME_BANNER_URL")
    or TICKET_WELCOME_BANNER_URL
).strip()
WELCOME_WEBSITE_URL = (os.environ.get("DISCORD_WELCOME_WEBSITE_URL") or "https://rivalsesports.games").strip()
WELCOME_RULES_URL = (os.environ.get("DISCORD_WELCOME_RULES_URL") or "https://rivalsesports.games/rules").strip()
XP_COOLDOWN_SECONDS = _env_int("DISCORD_XP_COOLDOWN_SECONDS", 60)
JOB_POLL_SECONDS = float((os.environ.get("DISCORD_JOB_POLL_SECONDS") or "2").strip() or 2)

# JSON example: {"5": 1234567890, "10": 1234567891}
LEVEL_ROLE_MAP = _env_json_object("DISCORD_LEVEL_ROLE_MAP", {})
STAFF_ROLE_IDS = _env_int_set(
    "DISCORD_STAFF_ROLE_IDS",
    {1366698520039526461, 1366698554822754394},
)
VIP_GOLD_ROLE_IDS = _env_int_set("DISCORD_VIP_GOLD_ROLE_IDS", set())
VIP_DIAMOND_ROLE_IDS = _env_int_set("DISCORD_VIP_DIAMOND_ROLE_IDS", set())
VIP_GOLD_XP_MULTIPLIER = 1.5
VIP_DIAMOND_XP_MULTIPLIER = 2.0


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_http_url(url: str) -> bool:
    u = (url or "").strip().lower()
    return u.startswith("http://") or u.startswith("https://")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def calc_level(xp: int) -> int:
    # Cheap deterministic curve
    return int((max(0, xp) // 100) ** 0.5)


def normalize_discord_username(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value.startswith("@"):
        value = value[1:]
    return value


def has_staff_access(member: discord.Member) -> bool:
    if not member:
        return False
    perms = member.guild_permissions
    if perms.administrator or perms.manage_guild or perms.manage_channels:
        return True
    return any(r.id in STAFF_ROLE_IDS for r in member.roles)


class RivalsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.guilds = True

        super().__init__(command_prefix="!", intents=intents)

        self.mongo = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        self.db = self.mongo[DB_NAME]

        self._xp_cooldowns = {}
        self._discord_call_gate = asyncio.Semaphore(2)
        if NEWS_BACKLOG_HOURS > 0:
            self._news_min_created_at = iso(now_utc() - timedelta(hours=NEWS_BACKLOG_HOURS))
        else:
            self._news_min_created_at = "1970-01-01T00:00:00+00:00"

    async def setup_hook(self):
        if DISCORD_GUILD_ID <= 0:
            logger.warning("DISCORD_GUILD_ID is not set. Bot features may not work correctly.")

        await self._ensure_discord_indexes()

        self.poll_jobs.change_interval(seconds=max(1.0, JOB_POLL_SECONDS))
        self.poll_jobs.start()

        self.add_view(TicketManageView(self))
        try:
            self.add_view(await self._build_ticket_panel_view())
        except Exception as exc:
            logger.warning("Ticket panel persistent view fallback enabled: %s", exc)
            self.add_view(TicketPanelView(self, []))

        await self._sync_app_commands()

    async def _sync_app_commands(self):
        """Best-effort command sync with duplicate-safe strategy (guild only)."""
        total_synced = 0

        # 1) Purge old global commands so they don't duplicate guild-scoped ones in slash UI.
        try:
            app_id = int(self.application_id) if self.application_id else None
            if not app_id:
                app_info = await asyncio.wait_for(self.application_info(), timeout=20)
                app_id = int(app_info.id)
            if app_id:
                await asyncio.wait_for(self.http.bulk_upsert_global_commands(app_id, []), timeout=20)
                logger.info("Global commands cleared to prevent slash duplication")
        except Exception as exc:
            logger.warning("Global command clear failed: %s", exc)

        # 2) Sync commands only for the configured guild.
        if DISCORD_GUILD_ID > 0:
            try:
                guild_obj = discord.Object(id=DISCORD_GUILD_ID)
                self.tree.copy_global_to(guild=guild_obj)
                synced_guild = await asyncio.wait_for(self.tree.sync(guild=guild_obj), timeout=20)
                total_synced += len(synced_guild)
                logger.info(
                    "Guild-only command sync complete (%s): %s commands",
                    DISCORD_GUILD_ID,
                    len(synced_guild),
                )
            except Exception as exc:
                logger.warning("Guild command sync failed (%s): %s", DISCORD_GUILD_ID, exc)
        else:
            logger.warning("DISCORD_GUILD_ID missing: guild-only command sync skipped")

        logger.info("Command sync finished. Total synced entries: %s", total_synced)

    async def on_ready(self):
        logger.info("Bot online as %s (%s)", self.user, self.user.id if self.user else "?")

    async def _ensure_discord_indexes(self):
        try:
            await self.db.discord_ticket_categories.create_index("id", unique=True)
            await self.db.discord_ticket_categories.create_index([
                ("guild_id", 1), ("is_active", 1), ("sort_order", 1), ("name", 1)
            ])
            await self.db.discord_tickets.create_index("id", unique=True)
            await self.db.discord_tickets.create_index([("guild_id", 1), ("channel_id", 1)], unique=True)
            await self.db.discord_tickets.create_index([
                ("guild_id", 1), ("creator_discord_id", 1), ("status", 1), ("created_at", -1)
            ])
            await self.db.discord_levels.create_index([("guild_id", 1), ("user_id", 1)], unique=True)
            await self.db.discord_level_roles.create_index([("guild_id", 1), ("level", 1)], unique=True)
            await self.db.discord_bot_settings.create_index([("guild_id", 1)], unique=True)
            await self.db.discord_jobs.create_index("id", unique=True)
            await self.db.discord_jobs.create_index(
                [("status", 1), ("next_retry_at", 1), ("priority", 1), ("created_at", 1)]
            )
        except Exception as exc:
            logger.warning("Ticket indexes init failed: %s", exc)

    async def close(self):
        try:
            if self.poll_jobs.is_running():
                self.poll_jobs.cancel()
        except Exception:
            pass
        try:
            self.mongo.close()
        except Exception:
            pass
        await super().close()

    async def _resolve_level_role_id(self, guild_id: int, level: int) -> Optional[int]:
        try:
            doc = await self.db.discord_level_roles.find_one(
                {"guild_id": guild_id, "level": int(level)},
                {"_id": 0, "role_id": 1},
            )
            if doc and str(doc.get("role_id") or "").isdigit():
                return int(doc["role_id"])
        except Exception:
            pass

        role_id = LEVEL_ROLE_MAP.get(str(int(level)))
        if str(role_id or "").isdigit():
            return int(role_id)
        return None

    async def _apply_level_role_if_any(self, member: discord.Member, level: int) -> bool:
        rid = await self._resolve_level_role_id(member.guild.id, int(level))
        if not rid:
            return False
        role = member.guild.get_role(rid)
        if not role:
            return False

        configured_ids = set()
        try:
            cfg_docs = await self.db.discord_level_roles.find(
                {"guild_id": member.guild.id},
                {"_id": 0, "role_id": 1},
            ).to_list(500)
            for d in cfg_docs:
                rv = d.get("role_id")
                if str(rv or "").isdigit():
                    configured_ids.add(int(rv))
        except Exception:
            pass
        for rv in LEVEL_ROLE_MAP.values():
            if str(rv or "").isdigit():
                configured_ids.add(int(rv))

        to_remove = [r for r in member.roles if r.id in configured_ids and r.id != rid]
        changed = False
        try:
            async with self._discord_call_gate:
                if to_remove:
                    await member.remove_roles(*to_remove, reason=f"RIVALS leveling swap L{level}")
                    changed = True
                if role not in member.roles:
                    await member.add_roles(role, reason=f"RIVALS leveling L{level}")
                    changed = True
            return changed
        except Exception:
            return False

    async def _grant_xp(self, member: discord.Member, gained: int, source: str = "slash") -> dict:
        gained = max(1, int(gained))
        after = await self.db.discord_levels.find_one_and_update(
            {"guild_id": member.guild.id, "user_id": member.id},
            {
                "$inc": {"xp": gained},
                "$set": {"username": str(member), "updated_at": iso(now_utc()), "last_source": source},
                "$setOnInsert": {"created_at": iso(now_utc()), "messages": 0, "level": 0},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        ) or {"xp": gained, "level": 0}

        old_level = int(after.get("level", 0) or 0)
        new_level = calc_level(int(after.get("xp", 0) or 0))
        leveled_up = new_level > old_level
        if new_level != old_level:
            await self.db.discord_levels.update_one(
                {"guild_id": member.guild.id, "user_id": member.id},
                {"$set": {"level": new_level}},
            )
        role_granted = False
        if leveled_up:
            role_granted = await self._apply_level_role_if_any(member, new_level)
        return {
            "xp": int(after.get("xp", 0) or 0),
            "old_level": old_level,
            "new_level": new_level,
            "leveled_up": leveled_up,
            "role_granted": role_granted,
        }

    def _vip_xp_multiplier_for_member(self, member: discord.Member) -> float:
        role_ids = {r.id for r in member.roles}
        if VIP_DIAMOND_ROLE_IDS and any(rid in role_ids for rid in VIP_DIAMOND_ROLE_IDS):
            return VIP_DIAMOND_XP_MULTIPLIER
        if VIP_GOLD_ROLE_IDS and any(rid in role_ids for rid in VIP_GOLD_ROLE_IDS):
            return VIP_GOLD_XP_MULTIPLIER

        role_names = {normalize_discord_username(r.name) for r in member.roles}
        if any("diamond" in rn or "دايموند" in rn for rn in role_names):
            return VIP_DIAMOND_XP_MULTIPLIER
        if any("gold" in rn or "جولد" in rn for rn in role_names):
            return VIP_GOLD_XP_MULTIPLIER
        return 1.0

    def _build_rank_embed(self, member: discord.Member, xp: int, level: int, gained: int = 0, multiplier: float = 1.0) -> discord.Embed:
        embed = discord.Embed(
            title="🎯 RIVALS Tactical Rank",
            description=f"{member.mention} استمر، ما باقي لك شيء.",
            color=discord.Color.blurple(),
            timestamp=now_utc(),
        )
        embed.add_field(name="Level", value=f"**{int(level)}**", inline=True)
        embed.add_field(name="XP", value=f"**{int(xp)}**", inline=True)
        embed.add_field(name="XP Gained", value=f"+{int(gained)}", inline=True)
        if multiplier > 1.0:
            embed.add_field(name="VIP Boost", value=f"x{multiplier:.1f}", inline=True)
        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass
        embed.set_footer(text="RIVALS XP System")
        return embed

    def _build_level_up_announcement_embed(
        self,
        member: discord.Member,
        new_level: int,
        role_name: str = "",
        multiplier: float = 1.0,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="🚀 LEVEL UP • RIVALS",
            description=f"{member.mention} دخل مستوى جديد! استمر، السيطرة جاية 🔥",
            color=discord.Color.gold(),
            timestamp=now_utc(),
        )
        embed.add_field(name="المستوى الجديد", value=f"**L{int(new_level)}**", inline=True)
        embed.add_field(name="الرتبة الجديدة", value=role_name or "—", inline=True)
        if multiplier > 1.0:
            embed.add_field(name="VIP Boost", value=f"x{multiplier:.1f}", inline=True)
        else:
            embed.add_field(name="VIP Boost", value="x1.0", inline=True)
        embed.set_footer(text="RIVALS Esports • Keep Grinding")
        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass
        return embed

    async def _resolve_level_up_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        # Priority 1: per-guild runtime setting via !set_level_channel
        try:
            cfg = await self.db.discord_bot_settings.find_one(
                {"guild_id": guild.id},
                {"_id": 0, "level_up_channel_id": 1},
            )
            cfg_id = int((cfg or {}).get("level_up_channel_id") or 0)
            if cfg_id > 0:
                ch = guild.get_channel(cfg_id)
                if isinstance(ch, discord.TextChannel):
                    return ch
        except Exception:
            pass

        # Priority 2: env LEVEL_UP_CHANNEL_ID
        if LEVEL_UP_CHANNEL_ID > 0:
            ch = guild.get_channel(LEVEL_UP_CHANNEL_ID)
            if isinstance(ch, discord.TextChannel):
                return ch

        # Priority 3: legacy rank channel
        if RANK_CHANNEL_ID > 0:
            ch = guild.get_channel(RANK_CHANNEL_ID)
            if isinstance(ch, discord.TextChannel):
                return ch

        # Priority 4: system channel then first writable text channel
        if isinstance(guild.system_channel, discord.TextChannel):
            return guild.system_channel
        me = guild.me
        for ch in guild.text_channels:
            if not me:
                return ch
            perms = ch.permissions_for(me)
            if perms.view_channel and perms.send_messages:
                return ch
        return None

    async def _guild(self) -> Optional[discord.Guild]:
        if DISCORD_GUILD_ID <= 0:
            return None
        g = self.get_guild(DISCORD_GUILD_ID)
        if g:
            return g
        try:
            return await self.fetch_guild(DISCORD_GUILD_ID)
        except Exception as exc:
            logger.warning("Failed to fetch guild: %s", exc)
            return None

    async def _resolve_member(self, guild: discord.Guild, discord_id: str) -> Optional[discord.Member]:
        if not discord_id or not str(discord_id).isdigit():
            return None
        uid = int(discord_id)
        m = guild.get_member(uid)
        if m:
            return m
        try:
            async with self._discord_call_gate:
                return await guild.fetch_member(uid)
        except Exception:
            return None

    async def _resolve_member_by_discord_username(self, guild: discord.Guild, discord_username: str) -> Optional[discord.Member]:
        target = normalize_discord_username(discord_username)
        if not target:
            return None

        def _matches(member: discord.Member) -> bool:
            if normalize_discord_username(member.name) == target:
                return True
            if normalize_discord_username(getattr(member, "global_name", "") or "") == target:
                return True
            return normalize_discord_username(member.display_name) == target

        for m in guild.members:
            if _matches(m):
                return m

        try:
            async with self._discord_call_gate:
                async for m in guild.fetch_members(limit=None):
                    if _matches(m):
                        return m
        except Exception:
            return None
        return None

    async def _resolve_member_from_user_doc(self, guild: discord.Guild, user_doc: dict) -> Optional[discord.Member]:
        if not user_doc:
            return None
        did = str(user_doc.get("discord_id") or "").strip()
        if did.isdigit():
            member = await self._resolve_member(guild, did)
            if member:
                return member
        return await self._resolve_member_by_discord_username(guild, str(user_doc.get("discord_username") or ""))

    async def _get_or_create_clan_role(self, guild: discord.Guild, clan_id: str, clan_name: str, clan_tag: str = "") -> Optional[discord.Role]:
        if not clan_id:
            return None

        role_doc = await self.db.discord_clan_roles.find_one({"clan_id": clan_id, "guild_id": guild.id}, {"_id": 0})
        if role_doc and role_doc.get("role_id"):
            role = guild.get_role(int(role_doc["role_id"]))
            if role:
                return role

        # Fallback by exact name to avoid duplicate roles
        target_name = f"{clan_name} [{clan_tag}]".strip()
        for r in guild.roles:
            if r.name == target_name:
                await self.db.discord_clan_roles.update_one(
                    {"clan_id": clan_id, "guild_id": guild.id},
                    {"$set": {"role_id": r.id, "updated_at": iso(now_utc())}},
                    upsert=True,
                )
                return r

        try:
            async with self._discord_call_gate:
                role = await guild.create_role(name=target_name, mentionable=True, reason="RIVALS clan role create")
            await self.db.discord_clan_roles.update_one(
                {"clan_id": clan_id, "guild_id": guild.id},
                {"$set": {"role_id": role.id, "clan_name": clan_name, "clan_tag": clan_tag, "updated_at": iso(now_utc())}},
                upsert=True,
            )
            return role
        except Exception as exc:
            logger.warning("Role create failed for clan %s: %s", clan_id, exc)
            return None

    async def _process_clan_role_create(self, payload: dict):
        guild = await self._guild()
        if not guild:
            return
        await self._get_or_create_clan_role(
            guild,
            payload.get("clan_id", ""),
            payload.get("clan_name", "Clan"),
            payload.get("clan_tag", ""),
        )

    async def _process_clan_role_sync_member(self, payload: dict):
        guild = await self._guild()
        if not guild:
            return

        user_id = payload.get("user_id", "")
        old_clan_id = (payload.get("old_clan_id") or "").strip()
        new_clan_id = (payload.get("new_clan_id") or "").strip()

        u = await self.db.users.find_one(
            {"id": user_id},
            {"_id": 0, "discord_id": 1, "discord_username": 1},
        )
        if not u:
            return

        member = await self._resolve_member_from_user_doc(guild, u)
        if not member:
            return

        if old_clan_id:
            old_role_doc = await self.db.discord_clan_roles.find_one({"clan_id": old_clan_id, "guild_id": guild.id}, {"_id": 0, "role_id": 1})
            if old_role_doc and old_role_doc.get("role_id"):
                old_role = guild.get_role(int(old_role_doc["role_id"]))
                if old_role and old_role in member.roles:
                    try:
                        async with self._discord_call_gate:
                            await member.remove_roles(old_role, reason="RIVALS clan sync")
                    except Exception as exc:
                        logger.warning("Failed remove old clan role: %s", exc)

        if new_clan_id:
            clan = await self.db.clans.find_one({"id": new_clan_id}, {"_id": 0, "id": 1, "name": 1, "tag": 1})
            if clan:
                new_role = await self._get_or_create_clan_role(guild, clan["id"], clan.get("name", "Clan"), clan.get("tag", ""))
                if new_role and new_role not in member.roles:
                    try:
                        async with self._discord_call_gate:
                            await member.add_roles(new_role, reason="RIVALS clan sync")
                    except Exception as exc:
                        logger.warning("Failed add new clan role: %s", exc)

    def _is_active_iso(self, raw_iso: str) -> bool:
        if not raw_iso:
            return False
        try:
            return datetime.fromisoformat(raw_iso) > now_utc()
        except Exception:
            return False

    def _user_has_plus_subscription(self, user_doc: dict) -> bool:
        return bool(
            user_doc.get("is_plus")
            or self._is_active_iso((user_doc.get("plus_expires_at") or "").strip())
            or self._is_active_iso((user_doc.get("personal_plus_until") or "").strip())
        )

    async def _sync_plus_role(self, member: discord.Member, user_doc: dict) -> bool:
        if PLUS_ROLE_ID <= 0:
            return False

        role = member.guild.get_role(PLUS_ROLE_ID)
        if not role:
            try:
                async with self._discord_call_gate:
                    role = await member.guild.fetch_role(PLUS_ROLE_ID)
            except Exception:
                return False
        if not role:
            return False

        has_plus = self._user_has_plus_subscription(user_doc)
        has_role = role in member.roles
        if has_plus and not has_role:
            async with self._discord_call_gate:
                await member.add_roles(role, reason="RIVALS plus sync")
            return True
        if (not has_plus) and has_role:
            async with self._discord_call_gate:
                await member.remove_roles(role, reason="RIVALS plus sync")
            return True
        return False

    async def _sync_clan_membership(self, member: discord.Member, user_doc: dict) -> bool:
        changed = False
        desired_clan_id = (user_doc.get("clan_id") or "").strip()

        role_docs = await self.db.discord_clan_roles.find(
            {"guild_id": member.guild.id},
            {"_id": 0, "clan_id": 1, "role_id": 1},
        ).to_list(500)
        for rd in role_docs:
            rid = rd.get("role_id")
            if not rid:
                continue
            try:
                rid_int = int(rid)
            except Exception:
                continue
            role = member.guild.get_role(rid_int)
            if role and role in member.roles and (rd.get("clan_id") or "") != desired_clan_id:
                try:
                    async with self._discord_call_gate:
                        await member.remove_roles(role, reason="RIVALS clan sync")
                    changed = True
                except Exception:
                    pass

        if desired_clan_id:
            clan = await self.db.clans.find_one(
                {"id": desired_clan_id},
                {"_id": 0, "id": 1, "name": 1, "tag": 1},
            )
            if clan:
                role = await self._get_or_create_clan_role(
                    member.guild,
                    clan["id"],
                    clan.get("name", "Clan"),
                    clan.get("tag", ""),
                )
                if role and role not in member.roles:
                    try:
                        async with self._discord_call_gate:
                            await member.add_roles(role, reason="RIVALS clan sync")
                        changed = True
                    except Exception:
                        pass

        return changed

    async def sync_member_from_site(self, member: discord.Member) -> dict:
        user_doc = await self.db.users.find_one(
            {"discord_id": str(member.id)},
            {
                "_id": 0,
                "id": 1,
                "clan_id": 1,
                "is_plus": 1,
                "plus_expires_at": 1,
                "personal_plus_until": 1,
                "discord_username": 1,
            },
        )
        if not user_doc:
            uname = normalize_discord_username(member.name)
            if uname:
                user_doc = await self.db.users.find_one(
                    {"discord_username": {"$regex": f"^{re.escape(uname)}$", "$options": "i"}},
                    {
                        "_id": 0,
                        "id": 1,
                        "clan_id": 1,
                        "is_plus": 1,
                        "plus_expires_at": 1,
                        "personal_plus_until": 1,
                        "discord_username": 1,
                    },
                )
        if not user_doc:
            return {"linked": False, "plus_changed": False, "clan_changed": False}

        plus_changed = False
        clan_changed = False
        try:
            plus_changed = await self._sync_plus_role(member, user_doc)
        except Exception as exc:
            logger.warning("Plus membership sync failed for %s: %s", member.id, exc)

        try:
            clan_changed = await self._sync_clan_membership(member, user_doc)
        except Exception as exc:
            logger.warning("Clan membership sync failed for %s: %s", member.id, exc)

        return {
            "linked": True,
            "plus_changed": plus_changed,
            "clan_changed": clan_changed,
            "clan_id": (user_doc.get("clan_id") or "").strip(),
            "plus_active": self._user_has_plus_subscription(user_doc),
        }

    async def _process_plus_channels_create(self, payload: dict):
        logger.info("Skipping plus channel creation job (role-only sync mode): %s", payload.get("clan_id", ""))

    async def _plus_room_doc_for_channel(self, guild_id: int, channel_id: int) -> Optional[dict]:
        return await self.db.discord_plus_channels.find_one(
            {
                "guild_id": guild_id,
                "$or": [
                    {"voice_channel_id": channel_id},
                    {"text_channel_id": channel_id},
                ],
            },
            {"_id": 0},
        )

    async def _plus_room_can_manage(self, member: discord.Member, plus_doc: dict) -> bool:
        clan_role_id = plus_doc.get("clan_role_id")
        if not clan_role_id and plus_doc.get("clan_id"):
            role_doc = await self.db.discord_clan_roles.find_one(
                {"guild_id": member.guild.id, "clan_id": plus_doc.get("clan_id")},
                {"_id": 0, "role_id": 1},
            )
            if role_doc and role_doc.get("role_id"):
                clan_role_id = role_doc.get("role_id")

        if not clan_role_id:
            return False

        try:
            clan_role_id_int = int(clan_role_id)
        except Exception:
            return False

        return any(r.id == clan_role_id_int for r in member.roles)

    async def _set_plus_room_visibility(self, guild: discord.Guild, plus_doc: dict, visible: bool, actor_id: int):
        voice_id = plus_doc.get("voice_channel_id")
        if not voice_id:
            raise RuntimeError("PLUS_ROOM_NOT_FOUND")

        voice_ch = guild.get_channel(int(voice_id))
        if not isinstance(voice_ch, discord.VoiceChannel):
            raise RuntimeError("PLUS_ROOM_NOT_FOUND")

        clan_role_id = plus_doc.get("clan_role_id")
        if not clan_role_id and plus_doc.get("clan_id"):
            role_doc = await self.db.discord_clan_roles.find_one(
                {"guild_id": guild.id, "clan_id": plus_doc.get("clan_id")},
                {"_id": 0, "role_id": 1},
            )
            if role_doc and role_doc.get("role_id"):
                clan_role_id = role_doc.get("role_id")

        clan_role = guild.get_role(int(clan_role_id)) if clan_role_id else None

        reason = f"RIVALS plus room visibility by {actor_id}"
        async with self._discord_call_gate:
            await voice_ch.set_permissions(
                guild.default_role,
                view_channel=visible,
                connect=False,
                speak=False,
                send_messages=False,
                reason=reason,
            )
            if clan_role:
                await voice_ch.set_permissions(
                    clan_role,
                    view_channel=True,
                    connect=True,
                    speak=True,
                    send_messages=True,
                    read_message_history=True,
                    mute_members=True,
                    deafen_members=True,
                    move_members=True,
                    reason=reason,
                )

    async def toggle_plus_visibility(self, member: discord.Member, channel: discord.abc.GuildChannel, visible: bool) -> str:
        plus_doc = await self._plus_room_doc_for_channel(member.guild.id, channel.id)
        if not plus_doc:
            return "❌ هذا الأمر يعمل فقط داخل شات روم البلس الصوتي الخاص بكم."

        can_manage = await self._plus_room_can_manage(member, plus_doc)
        if not can_manage:
            return "❌ لا تملك رتبة الكلان المرتبطة بهذا الروم."

        await self._set_plus_room_visibility(member.guild, plus_doc, visible=visible, actor_id=member.id)
        return "✅ تم إظهار الروم للجميع." if visible else "✅ تم إخفاء الروم عن الجميع."

    async def _process_moderation_sync(self, payload: dict):
        guild = await self._guild()
        if not guild:
            return

        u = await self.db.users.find_one({"id": payload.get("user_id", "")}, {"_id": 0, "discord_id": 1, "username": 1})
        if not u or not u.get("discord_id"):
            return

        action = (payload.get("action") or "").strip().lower()
        reason = (payload.get("reason") or "RIVALS moderation")[:200]
        member = await self._resolve_member(guild, str(u["discord_id"]))

        try:
            if action == "warn":
                if member:
                    async with self._discord_call_gate:
                        await member.send(f"⚠️ تحذير من الإدارة: {reason}")
                return

            if action in ("timeout", "remove_timeout") and member:
                until_iso = (payload.get("until") or "").strip()
                until_dt = None
                if action == "timeout" and until_iso:
                    try:
                        until_dt = datetime.fromisoformat(until_iso)
                    except Exception:
                        until_dt = now_utc() + timedelta(hours=1)
                async with self._discord_call_gate:
                    await member.edit(timed_out_until=until_dt, reason=reason)
                return

            if action == "ban":
                if member:
                    async with self._discord_call_gate:
                        await guild.ban(member, reason=reason, delete_message_days=0)
                else:
                    uid = int(str(u["discord_id"]))
                    usr_obj = discord.Object(id=uid)
                    async with self._discord_call_gate:
                        await guild.ban(usr_obj, reason=reason, delete_message_days=0)
                return

            if action == "unban":
                uid = int(str(u["discord_id"]))
                usr_obj = discord.Object(id=uid)
                async with self._discord_call_gate:
                    await guild.unban(usr_obj, reason=reason)
                return
        except Exception as exc:
            logger.warning("Moderation sync failed (%s): %s", action, exc)

    async def _news_channel(self) -> Optional[discord.TextChannel]:
        guild = await self._guild()
        if not guild or NEWS_CHANNEL_ID <= 0:
            logger.warning("News channel unavailable: guild=%s NEWS_CHANNEL_ID=%s", bool(guild), NEWS_CHANNEL_ID)
            return None
        ch = guild.get_channel(NEWS_CHANNEL_ID)
        if isinstance(ch, discord.TextChannel):
            return ch
        try:
            async with self._discord_call_gate:
                fetched = await guild.fetch_channel(NEWS_CHANNEL_ID)
            return fetched if isinstance(fetched, discord.TextChannel) else None
        except Exception:
            return None

    async def _welcome_channel(self) -> Optional[discord.TextChannel]:
        guild = await self._guild()
        if not guild or WELCOME_CHANNEL_ID <= 0:
            return None
        ch = guild.get_channel(WELCOME_CHANNEL_ID)
        if isinstance(ch, discord.TextChannel):
            return ch
        try:
            async with self._discord_call_gate:
                fetched = await guild.fetch_channel(WELCOME_CHANNEL_ID)
            return fetched if isinstance(fetched, discord.TextChannel) else None
        except Exception as exc:
            logger.warning("Welcome channel guild-fetch failed (%s): %s", WELCOME_CHANNEL_ID, exc)

        # Fallback: direct API fetch by channel id (helps when cache/guild lookup mismatches)
        try:
            async with self._discord_call_gate:
                fetched_any = await self.fetch_channel(WELCOME_CHANNEL_ID)
            return fetched_any if isinstance(fetched_any, discord.TextChannel) else None
        except Exception as exc:
            logger.warning("Welcome channel global-fetch failed (%s): %s", WELCOME_CHANNEL_ID, exc)
            return None

    def _build_welcome_embed(self, member: discord.Member) -> discord.Embed:
        embed = discord.Embed(
            title="🎉 عضو جديد وصل!",
            description=(
                f"هلا والله {member.mention}\n"
                f"نورت سيرفر **RIVALS** يا **{member.display_name}** 🔥"
            ),
            color=discord.Color.from_rgb(88, 101, 242),
            timestamp=now_utc(),
        )
        try:
            avatar_url = member.display_avatar.url
            embed.set_thumbnail(url=avatar_url)
            embed.set_author(name=str(member), icon_url=avatar_url)
        except Exception:
            pass

        if WELCOME_BANNER_URL:
            embed.set_image(url=WELCOME_BANNER_URL)

        embed.add_field(name="اسم العضو", value=member.display_name, inline=True)
        embed.add_field(name="الرقم", value=f"#{member.discriminator}", inline=True)
        embed.add_field(name="عدد الأعضاء", value=str(member.guild.member_count), inline=True)
        embed.set_footer(text="RIVALS VIP Welcome • أهلاً وسهلاً")
        return embed

    async def _clan_mention_or_name(self, guild: discord.Guild, clan: dict) -> str:
        if not clan:
            return "غير معروف"
        clan_id = (clan.get("id") or "").strip()
        clan_name = (clan.get("name") or "كلان").strip()
        if not clan_id:
            return clan_name

        role_doc = await self.db.discord_clan_roles.find_one(
            {"guild_id": guild.id, "clan_id": clan_id},
            {"_id": 0, "role_id": 1},
        )
        rid = str((role_doc or {}).get("role_id") or "").strip()
        if rid.isdigit():
            role = guild.get_role(int(rid))
            if role:
                return role.mention
        return clan_name

    async def _player_mention_or_name(self, user_id: str, fallback_username: str = "") -> str:
        if not user_id:
            return fallback_username or "لاعب"
        u = await self.db.users.find_one({"id": user_id}, {"_id": 0, "discord_id": 1, "username": 1})
        if not u:
            return fallback_username or "لاعب"
        did = str(u.get("discord_id") or "").strip()
        if did.isdigit():
            return f"<@{did}>"
        return (u.get("username") or fallback_username or "لاعب")

    async def _build_transfer_market_embed(self, guild: discord.Guild, doc: dict) -> discord.Embed:
        payload = doc.get("payload") or {}
        old_clan = payload.get("old_clan") or {}
        new_clan = payload.get("new_clan") or {}
        player = await self._player_mention_or_name(payload.get("user_id", ""), payload.get("username", ""))
        old_txt = await self._clan_mention_or_name(guild, old_clan)
        new_txt = await self._clan_mention_or_name(guild, new_clan)
        duration_label = (payload.get("duration_label") or "مدة غير متوفرة").strip()

        embed = discord.Embed(
            title="🔥 سوق الانتقالات • صفقة جديدة",
            description=(
                f"{player} انتقل من {old_txt} إلى {new_txt}\n"
                f"بعد أن قضى مدة {duration_label} في كلانه السابق."
            ),
            color=discord.Color.gold(),
            timestamp=now_utc(),
        )
        embed.add_field(name="الكلان السابق", value=old_txt, inline=True)
        embed.add_field(name="الكلان الجديد", value=new_txt, inline=True)
        embed.add_field(name="اللاعب", value=player, inline=True)
        logo = (new_clan.get("logo") or old_clan.get("logo") or "").strip()
        if logo:
            embed.set_thumbnail(url=logo)
        embed.set_footer(text="RIVALS • Clans Transfer Market")
        return embed

    def _build_match_start_embed(self, doc: dict) -> discord.Embed:
        payload = doc.get("payload") or {}
        clan_a = ((payload.get("clan_a") or {}).get("name") or "الفريق A").strip()
        clan_b = ((payload.get("clan_b") or {}).get("name") or "الفريق B").strip()
        title = (doc.get("title") or "انطلاق مباراة جديدة").strip()
        body = (doc.get("body") or f"{clan_a} ⚔️ {clan_b}").strip()
        embed = discord.Embed(
            title=f"🚀 {title}",
            description=body,
            color=discord.Color.blurple(),
            timestamp=now_utc(),
        )
        embed.set_footer(text="RIVALS • Match Center")
        return embed

    def _build_generic_news_embed(self, doc: dict) -> discord.Embed:
        kind = (doc.get("kind") or "news").strip()
        title = (doc.get("title") or "RIVALS News").strip()
        body = (doc.get("body") or "").strip()
        icon = "📰"
        color = discord.Color.blue()
        if kind == "hall-of-fame":
            icon = "🏆"
            color = discord.Color.gold()
        elif kind in {"match-score", "match-start"}:
            icon = "⚔️"
            color = discord.Color.blurple()
        elif kind == "transfer_market":
            icon = "🔥"
            color = discord.Color.orange()
        embed = discord.Embed(
            title=f"{icon} {title}",
            description=body or "—",
            color=color,
            timestamp=now_utc(),
        )
        embed.set_footer(text=f"RIVALS • {kind}")
        return embed

    async def _claim_pending_news_doc(self) -> Optional[dict]:
        q = {
            "$or": [{"discord_status": {"$exists": False}}, {"discord_status": "queued"}],
            "created_at": {"$gte": self._news_min_created_at},
        }
        return await self.db.news_posts.find_one_and_update(
            q,
            {"$set": {"discord_status": "processing", "discord_claimed_at": iso(now_utc())}},
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )

    async def _process_news_notifications(self):
        ch = await self._news_channel()
        if not ch:
            return

        doc = await self._claim_pending_news_doc()
        if not doc:
            return

        try:
            kind = (doc.get("kind") or "").strip()
            if kind == "transfer_market":
                embed = await self._build_transfer_market_embed(ch.guild, doc)
            elif kind == "match-start":
                embed = self._build_match_start_embed(doc)
            else:
                embed = self._build_generic_news_embed(doc)

            async with self._discord_call_gate:
                msg = await ch.send(embed=embed)

            await self.db.news_posts.update_one(
                {"id": doc["id"]},
                {
                    "$set": {
                        "discord_status": "posted",
                        "discord_posted_at": iso(now_utc()),
                        "discord_channel_id": ch.id,
                        "discord_message_id": msg.id,
                    }
                },
            )
        except Exception as exc:
            await self.db.news_posts.update_one(
                {"id": doc.get("id")},
                {
                    "$set": {
                        "discord_status": "queued",
                        "discord_last_error": str(exc)[:500],
                        "discord_updated_at": iso(now_utc()),
                    }
                },
            )

    async def _send_news_doc_to_channel(self, doc: dict) -> tuple[discord.TextChannel, discord.Message]:
        ch = await self._news_channel()
        if not ch:
            raise RuntimeError("NEWS_CHANNEL_ID is not reachable or not a text channel")
        kind = (doc.get("kind") or "").strip()
        if kind == "transfer_market":
            embed = await self._build_transfer_market_embed(ch.guild, doc)
        elif kind == "match-start":
            embed = self._build_match_start_embed(doc)
        else:
            embed = self._build_generic_news_embed(doc)
        async with self._discord_call_gate:
            msg = await ch.send(embed=embed)
        return ch, msg

    async def _process_news_job_payload(self, job_type: str, payload: dict):
        news_id = ((payload or {}).get("news_id") or "").strip()

        async def _mark_news_posted(ch_id: Optional[int], msg_id: Optional[int]):
            if not news_id:
                return
            await self.db.news_posts.update_one(
                {"id": news_id},
                {
                    "$set": {
                        "discord_status": "posted",
                        "discord_posted_at": iso(now_utc()),
                        "discord_channel_id": ch_id,
                        "discord_message_id": msg_id,
                        "discord_updated_at": iso(now_utc()),
                        "discord_last_error": "",
                    }
                },
            )

        async def _mark_news_failed(exc: Exception):
            if not news_id:
                return
            await self.db.news_posts.update_one(
                {"id": news_id},
                {
                    "$set": {
                        "discord_status": "queued",
                        "discord_last_error": str(exc)[:500],
                        "discord_updated_at": iso(now_utc()),
                    }
                },
            )

        if job_type == "news_transfer_market":
            try:
                ch, msg = await self._send_news_doc_to_channel({"kind": "transfer_market", "payload": payload or {}})
                await _mark_news_posted(getattr(ch, "id", None), getattr(msg, "id", None))
            except Exception as exc:
                await _mark_news_failed(exc)
                raise
            return

        if job_type == "news_match_start":
            try:
                ch, msg = await self._send_news_doc_to_channel(
                    {
                        "kind": "match-start",
                        "title": (payload or {}).get("title", "انطلاق مباراة جديدة"),
                        "body": (payload or {}).get("body", ""),
                        "payload": payload or {},
                    }
                )
                await _mark_news_posted(getattr(ch, "id", None), getattr(msg, "id", None))
            except Exception as exc:
                await _mark_news_failed(exc)
                raise
            return

        if job_type == "news_match_score":
            # Disabled by product policy (start-only match alerts)
            return

        # Generic hook for backend custom news payloads (supports all kinds)
        kind = ((payload or {}).get("kind") or "news").strip()
        try:
            ch, msg = await self._send_news_doc_to_channel(
                {
                    "kind": kind,
                    "title": (payload or {}).get("title", "RIVALS News"),
                    "body": (payload or {}).get("body", ""),
                    "payload": (payload or {}).get("payload") or payload or {},
                }
            )
            await _mark_news_posted(getattr(ch, "id", None), getattr(msg, "id", None))
        except Exception as exc:
            await _mark_news_failed(exc)
            raise

    def _slugify_channel_name(self, text: str) -> str:
        s = re.sub(r"[^\w\-\s]", "", (text or "").strip().lower(), flags=re.UNICODE)
        s = re.sub(r"\s+", "-", s)
        s = re.sub(r"-+", "-", s).strip("-")
        return s[:80] or "ticket"

    def _parse_option_emoji(self, raw: str):
        val = (raw or "").strip()
        if not val:
            return None
        try:
            if val.startswith("<") and val.endswith(">"):
                return discord.PartialEmoji.from_str(val)
            return val
        except Exception:
            return None

    async def _ticket_categories(self, guild_id: int, active_only: bool = True) -> List[dict]:
        q = {"guild_id": guild_id}
        if active_only:
            q["is_active"] = True
        try:
            return await self.db.discord_ticket_categories.find(q, {"_id": 0}).sort([
                ("sort_order", 1), ("name", 1)
            ]).to_list(50)
        except Exception as exc:
            logger.warning("Ticket categories load failed: %s", exc)
            return []

    async def _build_ticket_panel_view(self) -> "TicketPanelView":
        guild_id = DISCORD_GUILD_ID if DISCORD_GUILD_ID > 0 else 0
        categories = await self._ticket_categories(guild_id, active_only=True) if guild_id else []
        options: List[discord.SelectOption] = []
        for c in categories[:25]:
            options.append(
                discord.SelectOption(
                    label=(c.get("name") or "Support")[:100],
                    description=(c.get("description") or "")[:100] or "فتح تذكرة دعم",
                    value=str(c.get("id", "")),
                    emoji=self._parse_option_emoji(c.get("emoji", "")),
                )
            )
        return TicketPanelView(self, options)

    def build_ticket_panel_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎫 نظام تذاكر الدعم الفني",
            description=(
                "مرحباً بك في مركز الدعم.\n"
                "اختر القسم المناسب من القائمة المنسدلة أدناه، وسيتم فتح تذكرتك بشكل خاص وفوري."
            ),
            color=discord.Color.dark_teal(),
            timestamp=now_utc(),
        )
        embed.set_footer(text="RIVALS Support Center • Dynamic Ticket System")
        if TICKET_PANEL_BANNER_GIF_URL:
            embed.set_image(url=TICKET_PANEL_BANNER_GIF_URL)
        return embed

    async def _resolve_custom_emoji_literal(self, guild: discord.Guild, emoji_name: str) -> Optional[str]:
        name = (emoji_name or "").strip().strip(":")
        if not name:
            return None

        for e in guild.emojis:
            if e.name == name:
                return str(e)
        return None

    async def add_ticket_category(
        self,
        guild: discord.Guild,
        name: str,
        description: Optional[str] = None,
        emoji_literal: Optional[str] = None,
        category_id: Optional[int] = None,
        support_role_id: Optional[int] = None,
    ) -> dict:
        safe_name = (name or "").strip()

        if not safe_name:
            raise ValueError("اسم القسم مطلوب")

        existing = await self.db.discord_ticket_categories.find_one(
            {
                "guild_id": guild.id,
                "name": {"$regex": f"^{re.escape(safe_name)}$", "$options": "i"},
            },
            {
                "_id": 0,
                "id": 1,
                "sort_order": 1,
                "description": 1,
                "emoji": 1,
                "discord_category_id": 1,
                "support_role_id": 1,
                "is_active": 1,
            },
        )

        max_sort_doc = await self.db.discord_ticket_categories.find_one(
            {"guild_id": guild.id},
            {"_id": 0, "sort_order": 1},
            sort=[("sort_order", -1)],
        )
        next_sort = int((max_sort_doc or {}).get("sort_order") or 0) + 1

        category_id_value = (existing or {}).get("id") or f"ticket_cat_{int(now_utc().timestamp())}_{random.randint(1000, 9999)}"

        set_doc = {
            "guild_id": guild.id,
            "id": category_id_value,
            "name": safe_name[:100],
            "is_active": True,
            "sort_order": int((existing or {}).get("sort_order") or next_sort),
            "updated_at": iso(now_utc()),
        }

        if description is not None:
            set_doc["description"] = (description or "").strip()[:180]
        if emoji_literal is not None:
            set_doc["emoji"] = emoji_literal
        if category_id is not None:
            set_doc["discord_category_id"] = str(category_id)
        if support_role_id is not None:
            set_doc["support_role_id"] = str(support_role_id)

        if not existing:
            missing_required = []
            if description is None:
                missing_required.append("description")
            if emoji_literal is None:
                missing_required.append("emoji_name")
            if category_id is None:
                missing_required.append("category_id")
            if support_role_id is None:
                missing_required.append("support_role_id")
            if missing_required:
                raise ValueError(
                    "لإضافة قسم جديد يجب تعبئة الحقول: " + ", ".join(missing_required)
                )

        await self.db.discord_ticket_categories.update_one(
            {"guild_id": guild.id, "id": category_id_value},
            {"$set": set_doc, "$setOnInsert": {"created_at": iso(now_utc())}},
            upsert=True,
        )

        saved = await self.db.discord_ticket_categories.find_one(
            {"guild_id": guild.id, "id": category_id_value},
            {"_id": 0},
        )
        return saved or set_doc

    async def refresh_ticket_panel_messages(self, guild: discord.Guild) -> tuple[int, int]:
        updated = 0
        failed = 0
        view = await self._build_ticket_panel_view()
        embed = self.build_ticket_panel_embed()

        me = guild.me
        if not me:
            return 0, 0

        for ch in guild.text_channels:
            perms = ch.permissions_for(me)
            if not (perms.view_channel and perms.read_message_history):
                continue

            try:
                async with self._discord_call_gate:
                    history = ch.history(limit=100)
                async for msg in history:
                    if not self.user or msg.author.id != self.user.id:
                        continue

                    has_ticket_select = False
                    for row in (msg.components or []):
                        for comp in getattr(row, "children", []):
                            if getattr(comp, "custom_id", "") == "rivals:tickets:select":
                                has_ticket_select = True
                                break
                        if has_ticket_select:
                            break

                    if not has_ticket_select:
                        continue

                    try:
                        async with self._discord_call_gate:
                            await msg.edit(embed=embed, view=view)
                        updated += 1
                    except Exception:
                        failed += 1
            except Exception:
                continue

        return updated, failed

    async def _ticket_category_doc(self, guild_id: int, ticket_category_id: str) -> Optional[dict]:
        if not ticket_category_id:
            return None
        try:
            return await self.db.discord_ticket_categories.find_one(
                {"guild_id": guild_id, "id": ticket_category_id, "is_active": True},
                {"_id": 0},
            )
        except Exception as exc:
            logger.warning("Ticket category lookup failed: %s", exc)
            return None

    async def _resolve_ticket_support_role(self, guild: discord.Guild, ticket_category: dict) -> Optional[discord.Role]:
        rid = str(ticket_category.get("support_role_id") or "").strip()
        if not rid.isdigit():
            return None
        role = guild.get_role(int(rid))
        if role:
            return role
        try:
            async with self._discord_call_gate:
                return await guild.fetch_role(int(rid))
        except Exception:
            return None

    async def _find_open_ticket(self, guild_id: int, creator_discord_id: int, ticket_category_id: str) -> Optional[dict]:
        try:
            return await self.db.discord_tickets.find_one(
                {
                    "guild_id": guild_id,
                    "creator_discord_id": creator_discord_id,
                    "ticket_category_id": ticket_category_id,
                    "status": "open",
                },
                {"_id": 0},
                sort=[("created_at", -1)],
            )
        except Exception as exc:
            logger.warning("Open ticket lookup failed: %s", exc)
            return None

    async def _create_ticket_channel(
        self,
        guild: discord.Guild,
        member: discord.Member,
        ticket_category: dict,
        subject: str = "",
        message: str = "",
        requested_by: str = "bot",
    ) -> tuple[Optional[discord.TextChannel], bool, str]:
        tcat_id = str(ticket_category.get("id") or "").strip()
        if not tcat_id:
            return None, False, "تعذر تحديد فئة التذكرة."

        existing = await self._find_open_ticket(guild.id, member.id, tcat_id)
        if existing and str(existing.get("channel_id", "")).isdigit():
            ch0 = guild.get_channel(int(existing["channel_id"]))
            if isinstance(ch0, discord.TextChannel):
                return ch0, False, "لديك تذكرة مفتوحة مسبقاً في هذا القسم."
            await self.db.discord_tickets.update_one(
                {"id": existing.get("id")},
                {"$set": {"status": "closed", "closed_reason": "channel_missing", "updated_at": iso(now_utc())}},
            )

        support_role = await self._resolve_ticket_support_role(guild, ticket_category)

        category_obj = None
        dcid = str(ticket_category.get("discord_category_id") or "").strip()
        if dcid.isdigit():
            category_obj = guild.get_channel(int(dcid))

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)

        name_part = self._slugify_channel_name(ticket_category.get("name", "support"))
        user_part = self._slugify_channel_name(member.display_name)
        channel_name = f"{name_part}-{user_part}"[:90]

        try:
            async with self._discord_call_gate:
                ch = await guild.create_text_channel(
                    name=channel_name,
                    category=category_obj,
                    overwrites=overwrites,
                    reason=f"RIVALS ticket: {ticket_category.get('name', 'support')}",
                )
        except Exception as exc:
            logger.warning("Ticket channel create failed: %s", exc)
            return None, False, "تعذر إنشاء قناة التذكرة حالياً."

        tdoc = {
            "id": f"ticket_{ch.id}",
            "guild_id": guild.id,
            "channel_id": ch.id,
            "creator_discord_id": member.id,
            "creator_username": str(member),
            "ticket_category_id": tcat_id,
            "ticket_category_name": ticket_category.get("name", "support"),
            "discord_category_id": str(ticket_category.get("discord_category_id") or ""),
            "support_role_id": str(ticket_category.get("support_role_id") or ""),
            "status": "open",
            "requested_by": requested_by,
            "subject": (subject or "")[:160],
            "first_message": (message or "")[:2000],
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        }
        try:
            await self.db.discord_tickets.update_one(
                {"guild_id": guild.id, "channel_id": ch.id},
                {"$set": tdoc},
                upsert=True,
            )
        except Exception as exc:
            logger.warning("Ticket save failed: %s", exc)

        support_mention = support_role.mention if support_role else ""
        welcome = (
            f"🎫 أهلاً {member.mention}\n"
            f"**القسم:** {ticket_category.get('name', 'Support')}\n"
            f"{support_mention}\n"
            f"يرجى وصف طلبك بالتفصيل وسيقوم فريق الدعم بالرد قريباً."
        )
        if subject:
            welcome += f"\n**الموضوع:** {subject[:160]}"
        if message:
            welcome += f"\n{message[:1200]}"

        try:
            embed = discord.Embed(color=discord.Color.dark_teal())
            embed.set_image(url=TICKET_WELCOME_BANNER_URL)
            await ch.send(content=welcome, embed=embed, view=TicketManageView(self))
        except Exception as exc:
            logger.warning("Ticket welcome send failed: %s", exc)

        return ch, True, "تم فتح التذكرة بنجاح."

    async def _ticket_doc_by_channel(self, guild_id: int, channel_id: int) -> Optional[dict]:
        try:
            return await self.db.discord_tickets.find_one(
                {"guild_id": guild_id, "channel_id": channel_id},
                {"_id": 0},
            )
        except Exception as exc:
            logger.warning("Ticket-by-channel lookup failed: %s", exc)
            return None

    async def _can_manage_ticket(self, member: discord.Member, ticket_doc: dict) -> bool:
        if member.guild_permissions.manage_channels:
            return True
        if int(ticket_doc.get("creator_discord_id") or 0) == member.id:
            return True
        support_role_id = str(ticket_doc.get("support_role_id") or "").strip()
        if support_role_id.isdigit() and any(r.id == int(support_role_id) for r in member.roles):
            return True
        return False

    async def close_ticket_channel(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.channel:
            await interaction.response.send_message("❌ هذا الإجراء يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ هذا الأمر للتذاكر النصية فقط.", ephemeral=True)
            return

        ticket = await self._ticket_doc_by_channel(interaction.guild.id, interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ هذه القناة ليست تذكرة معروفة.", ephemeral=True)
            return

        if not await self._can_manage_ticket(interaction.user, ticket):
            await interaction.response.send_message("❌ لا تملك صلاحية إغلاق هذه التذكرة.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=False, thinking=False)

        await self.db.discord_tickets.update_one(
            {"guild_id": interaction.guild.id, "channel_id": interaction.channel.id},
            {
                "$set": {
                    "status": "closed",
                    "closed_at": iso(now_utc()),
                    "closed_by_discord_id": interaction.user.id,
                    "updated_at": iso(now_utc()),
                }
            },
        )

        await interaction.followup.send("✅ تم إغلاق التذكرة. سيتم حذف القناة خلال 5 ثوان.", ephemeral=False)

        await asyncio.sleep(5)
        try:
            async with self._discord_call_gate:
                await interaction.channel.delete(reason=f"RIVALS ticket closed by {interaction.user.id}")
        except Exception as exc:
            logger.warning("Ticket delete failed: %s", exc)

    async def archive_ticket_channel(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.channel:
            await interaction.response.send_message("❌ هذا الإجراء يعمل داخل السيرفر فقط.", ephemeral=True)
            return
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ هذا الأمر للتذاكر النصية فقط.", ephemeral=True)
            return

        ticket = await self._ticket_doc_by_channel(interaction.guild.id, interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ هذه القناة ليست تذكرة معروفة.", ephemeral=True)
            return

        if not await self._can_manage_ticket(interaction.user, ticket):
            await interaction.response.send_message("❌ لا تملك صلاحية أرشفة هذه التذكرة.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=False, thinking=False)

        creator_id = int(ticket.get("creator_discord_id") or 0)
        creator_member = interaction.guild.get_member(creator_id) if creator_id else None
        try:
            async with self._discord_call_gate:
                if creator_member:
                    await interaction.channel.set_permissions(
                        creator_member,
                        view_channel=True,
                        send_messages=False,
                        read_message_history=True,
                        reason=f"RIVALS ticket archived by {interaction.user.id}",
                    )
                if not interaction.channel.name.startswith("archived-"):
                    await interaction.channel.edit(name=(f"archived-{interaction.channel.name}"[:90]))
        except Exception as exc:
            logger.warning("Ticket archive lock failed: %s", exc)

        await self.db.discord_tickets.update_one(
            {"guild_id": interaction.guild.id, "channel_id": interaction.channel.id},
            {
                "$set": {
                    "status": "archived",
                    "archived_at": iso(now_utc()),
                    "archived_by_discord_id": interaction.user.id,
                    "updated_at": iso(now_utc()),
                }
            },
        )

        await interaction.followup.send("🗂️ تم أرشفة التذكرة وقفلها.", ephemeral=False)

    async def create_ticket_from_dropdown(self, interaction: discord.Interaction, ticket_category_id: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ هذا الإجراء يعمل داخل السيرفر فقط.", ephemeral=True)
            return

        tcat = await self._ticket_category_doc(interaction.guild.id, ticket_category_id)
        if not tcat:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ فئة التذكرة غير متاحة حالياً.", ephemeral=True)
            else:
                await interaction.followup.send("❌ فئة التذكرة غير متاحة حالياً.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)

        ch, created, msg = await self._create_ticket_channel(
            guild=interaction.guild,
            member=interaction.user,
            ticket_category=tcat,
            subject=f"طلب من {interaction.user.display_name}",
            message="",
            requested_by="panel_select",
        )
        if ch:
            await interaction.followup.send(
                f"{'✅' if created else 'ℹ️'} {msg}\nالقناة: {ch.mention}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)

        # Reset the main ticket dropdown state immediately after selection
        try:
            if interaction.message:
                refreshed_view = await self._build_ticket_panel_view()
                await interaction.message.edit(view=refreshed_view)
        except Exception as exc:
            logger.warning("Ticket panel refresh after select failed: %s", exc)

    async def _process_ticket_create(self, payload: dict):
        guild = await self._guild()
        if not guild:
            return

        u = await self.db.users.find_one({"id": payload.get("user_id", "")}, {"_id": 0, "discord_id": 1, "username": 1})
        if not u or not u.get("discord_id"):
            return

        member = await self._resolve_member(guild, str(u["discord_id"]))
        if not member:
            return

        ticket_category_id = str(payload.get("ticket_category_id") or "").strip()
        tcat = await self._ticket_category_doc(guild.id, ticket_category_id) if ticket_category_id else None

        if not tcat:
            cats = await self._ticket_categories(guild.id, active_only=True)
            if cats:
                tcat = cats[0]

        if not tcat:
            tcat = {
                "id": "legacy_default",
                "name": "الدعم الفني",
                "description": "",
                "emoji": "🎫",
                "discord_category_id": str(TICKET_CATEGORY_ID or ""),
                "support_role_id": str(SUPPORT_ROLE_ID or ""),
            }

        _, _, msg = await self._create_ticket_channel(
            guild=guild,
            member=member,
            ticket_category=tcat,
            subject=(payload.get("subject") or "دعم عام"),
            message=(payload.get("message") or ""),
            requested_by="job_queue",
        )
        logger.info("Ticket create processed: %s", msg)

    async def _handle_job(self, job: dict):
        t = job.get("type", "")
        payload = job.get("payload", {}) or {}

        if t == "clan_role_create":
            await self._process_clan_role_create(payload)
        elif t == "clan_role_sync_member":
            await self._process_clan_role_sync_member(payload)
        elif t == "plus_channels_create":
            await self._process_plus_channels_create(payload)
        elif t == "moderation_sync":
            await self._process_moderation_sync(payload)
        elif t == "ticket_create":
            await self._process_ticket_create(payload)
        elif t in ("news_transfer_market", "news_match_start", "news_match_score", "news_post"):
            await self._process_news_job_payload(t, payload)

    @tasks.loop(seconds=2)
    async def poll_jobs(self):
        if not self.is_ready():
            return

        now = iso(now_utc())
        job = await self.db.discord_jobs.find_one_and_update(
            {
                "status": "queued",
                "$or": [{"next_retry_at": {"$exists": False}}, {"next_retry_at": {"$lte": now}}],
            },
            {"$set": {"status": "processing", "updated_at": now}, "$inc": {"attempts": 1}},
            sort=[("priority", 1), ("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        if job:
            try:
                await self._handle_job(job)
                await self.db.discord_jobs.update_one(
                    {"id": job["id"]},
                    {"$set": {"status": "done", "updated_at": iso(now_utc()), "last_error": ""}},
                )
            except Exception as exc:
                attempts = int(job.get("attempts", 1))
                delay = min(600, 2 ** min(8, attempts))
                retry_at = iso(now_utc() + timedelta(seconds=delay))
                await self.db.discord_jobs.update_one(
                    {"id": job["id"]},
                    {
                        "$set": {
                            "status": "queued" if attempts < 8 else "failed",
                            "updated_at": iso(now_utc()),
                            "last_error": str(exc)[:800],
                            "next_retry_at": retry_at,
                        }
                    },
                )

        try:
            await self._process_news_notifications()
        except Exception as exc:
            logger.warning("News notification loop failed: %s", exc)

    @poll_jobs.before_loop
    async def before_poll_jobs(self):
        await self.wait_until_ready()

    @poll_jobs.error
    async def poll_jobs_error(self, exc: Exception):
        logger.exception("poll_jobs loop crashed: %s", exc)

    async def on_member_join(self, member: discord.Member):
        if member.guild.id != DISCORD_GUILD_ID:
            return

        ch = await self._welcome_channel()
        if ch:
            try:
                await ch.send(
                    content=f"👋 أهلاً {member.mention}",
                    embed=self._build_welcome_embed(member),
                    view=WelcomeLinksView(),
                )
            except Exception as exc:
                logger.warning("Welcome send failed in #%s: %s", ch.id, exc)

        # One-shot site sync on join (Plus + Clan)
        await self.sync_member_from_site(member)

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or message.guild.id != DISCORD_GUILD_ID:
            return

        # Leveling from normal messages
        key = (message.guild.id, message.author.id)
        now_ts = now_utc().timestamp()
        if now_ts >= self._xp_cooldowns.get(key, 0):
            self._xp_cooldowns[key] = now_ts + XP_COOLDOWN_SECONDS
            base_gain = random.randint(8, 15)
            multiplier = self._vip_xp_multiplier_for_member(message.author)
            gained = max(1, int(round(base_gain * multiplier)))
            res = await self._grant_xp(message.author, gained, source="message")
            if res.get("leveled_up") or res.get("role_granted"):
                announce_channel = await self._resolve_level_up_channel(message.guild)
                if announce_channel:
                    role_id = await self._resolve_level_role_id(message.guild.id, int(res.get("new_level", 0) or 0))
                    role_name = ""
                    if role_id:
                        role_obj = message.guild.get_role(int(role_id))
                        if role_obj:
                            role_name = role_obj.name
                    try:
                        embed = self._build_level_up_announcement_embed(
                            message.author,
                            new_level=int(res.get("new_level", 0) or 0),
                            role_name=role_name,
                            multiplier=multiplier,
                        )
                        content = f"🎉 {message.author.mention}"
                        async with self._discord_call_gate:
                            await announce_channel.send(content=content, embed=embed)
                    except Exception:
                        pass

        await self.process_commands(message)


bot = RivalsBot()


class TicketManageView(discord.ui.View):
    def __init__(self, bot_ref: RivalsBot):
        super().__init__(timeout=None)
        self.bot_ref = bot_ref
        self.add_item(TicketManageSelect(bot_ref))


class TicketManageSelect(discord.ui.Select):
    def __init__(self, bot_ref: RivalsBot):
        options = [
            discord.SelectOption(
                label="🔒 قفل وأرشفة التذكرة",
                description="Archive / Lock",
                value="archive",
                emoji="🔒",
            ),
            discord.SelectOption(
                label="❌ إغلاق التذكرة نهائياً",
                description="Close",
                value="close",
                emoji="❌",
            ),
        ]
        super().__init__(
            placeholder="إدارة التذكرة...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="rivals:ticket:manage-select",
        )
        self.bot_ref = bot_ref

    async def callback(self, interaction: discord.Interaction):
        selected = (self.values or [""])[0]
        if selected == "archive":
            await self.bot_ref.archive_ticket_channel(interaction)
            return
        if selected == "close":
            await self.bot_ref.close_ticket_channel(interaction)
            return
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ خيار غير معروف.", ephemeral=True)


class TicketCategorySelect(discord.ui.Select):
    def __init__(self, bot_ref: RivalsBot, options: List[discord.SelectOption]):
        super().__init__(
            placeholder="...اختر نوع التذكره",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="rivals:tickets:select",
        )
        self.bot_ref = bot_ref

    async def callback(self, interaction: discord.Interaction):
        selected = (self.values or [""])[0]
        await self.bot_ref.create_ticket_from_dropdown(interaction, selected)


class TicketPanelView(discord.ui.View):
    def __init__(self, bot_ref: RivalsBot, options: List[discord.SelectOption]):
        super().__init__(timeout=None)
        if not options:
            options = [
                discord.SelectOption(
                    label="لا توجد أقسام متاحة حالياً",
                    description="يرجى التواصل مع الإدارة",
                    value="unavailable",
                    emoji="⏳",
                )
            ]
        select = TicketCategorySelect(bot_ref, options)
        if options and options[0].value == "unavailable":
            select.disabled = True
        self.add_item(select)


class WelcomeLinksView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        if _is_http_url(WELCOME_WEBSITE_URL):
            self.add_item(
                discord.ui.Button(
                    label="الموقع",
                    style=discord.ButtonStyle.link,
                    url=WELCOME_WEBSITE_URL,
                    emoji="🌐",
                )
            )
        if _is_http_url(WELCOME_RULES_URL):
            self.add_item(
                discord.ui.Button(
                    label="القوانين",
                    style=discord.ButtonStyle.link,
                    url=WELCOME_RULES_URL,
                    emoji="📜",
                )
            )


@bot.command(name="ticket")
async def ticket_cmd(ctx: commands.Context, *, subject: str = "دعم عام"):
    if not isinstance(ctx.author, discord.Member) or not ctx.guild:
        await ctx.reply("❌ هذا الأمر داخل السيرفر فقط.", mention_author=False)
        return
    if not has_staff_access(ctx.author):
        await ctx.reply("❌ هذا الأمر مخصص للإدارة فقط.", mention_author=False)
        return
    payload = {
        "user_id": str(ctx.author.id),
        "subject": subject,
        "message": "طلب دعم من أمر !ticket",
    }
    await bot._process_ticket_create(payload)
    await ctx.reply("✅ تم فتح تذكرة الدعم.", mention_author=False)


@bot.command(name="ticketpanel")
async def ticket_panel_cmd(ctx: commands.Context):
    if not isinstance(ctx.author, discord.Member) or not ctx.guild:
        await ctx.reply("❌ هذا الأمر داخل السيرفر فقط.", mention_author=False)
        return
    if not has_staff_access(ctx.author):
        await ctx.reply("❌ ليس لديك صلاحية نشر لوحة التذاكر.", mention_author=False)
        return

    view = await bot._build_ticket_panel_view()
    embed = bot.build_ticket_panel_embed()

    await ctx.send(embed=embed, view=view)
    await ctx.reply("✅ تم نشر لوحة التذاكر.", mention_author=False)


@bot.command(name="syncme")
async def syncme_cmd(ctx: commands.Context):
    u = await bot.db.users.find_one(
        {"discord_id": str(ctx.author.id)},
        {"_id": 0, "id": 1, "clan_id": 1, "discord_username": 1},
    )
    if not u:
        uname = normalize_discord_username(getattr(ctx.author, "name", ""))
        if uname:
            u = await bot.db.users.find_one(
                {"discord_username": {"$regex": f"^{re.escape(uname)}$", "$options": "i"}},
                {"_id": 0, "id": 1, "clan_id": 1, "discord_username": 1},
            )
    if not u:
        await ctx.reply("حسابك غير مرتبط بالمنصة بعد.", mention_author=False)
        return

    await bot._process_clan_role_sync_member(
        {"user_id": u["id"], "old_clan_id": "", "new_clan_id": u.get("clan_id") or ""}
    )
    await ctx.reply("✅ تمت مزامنة الرتبة.", mention_author=False)


@bot.command(name="sync")
async def sync_cmd(ctx: commands.Context):
    if not isinstance(ctx.author, discord.Member) or not ctx.guild:
        await ctx.reply("❌ هذا الأمر داخل السيرفر فقط.", mention_author=False)
        return
    result = await bot.sync_member_from_site(ctx.author)
    if not result.get("linked"):
        await ctx.reply("❌ حسابك غير مرتبط بالموقع بعد.", mention_author=False)
        return
    await ctx.reply(
        (
            "✅ تمت مزامنة عضويتك من الموقع.\n"
            f"• Plus: {'نشط' if result.get('plus_active') else 'غير نشط'}\n"
            f"• Clan: {(result.get('clan_id') or 'بدون كلان')}"
        ),
        mention_author=False,
    )


@bot.tree.command(name="sync", description="مزامنة اشتراك Plus ورتبة الكلان من الموقع")
async def sync_slash(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    result = await bot.sync_member_from_site(interaction.user)
    if not result.get("linked"):
        await interaction.followup.send("❌ حسابك غير مرتبط بالموقع بعد.", ephemeral=True)
        return

    await interaction.followup.send(
        (
            "✅ تمت مزامنة عضويتك من الموقع.\n"
            f"• Plus: {'نشط' if result.get('plus_active') else 'غير نشط'}\n"
            f"• Clan: {(result.get('clan_id') or 'بدون كلان')}"
        ),
        ephemeral=True,
    )


@bot.tree.command(name="news_test", description="اختبار قناة الأخبار في الديسكورد")
async def news_test_slash(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
        return
    if not has_staff_access(interaction.user):
        await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة فقط.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    ch = await bot._news_channel()
    if not ch:
        await interaction.followup.send(
            f"❌ تعذر الوصول لقناة الأخبار. تحقق من DISCORD_NEWS_CHANNEL_ID الحالي: `{NEWS_CHANNEL_ID}`",
            ephemeral=True,
        )
        return
    try:
        embed = discord.Embed(
            title="✅ اختبار قناة الأخبار",
            description="إذا وصلك هذا الإعلان فالبوت قادر على نشر الأخبار بشكل سليم.",
            color=discord.Color.green(),
            timestamp=now_utc(),
        )
        embed.set_footer(text="RIVALS • News Test")
        async with bot._discord_call_gate:
            msg = await ch.send(embed=embed)
        await interaction.followup.send(
            f"✅ تم الإرسال بنجاح إلى {ch.mention} (message_id={msg.id})",
            ephemeral=True,
        )
    except Exception as exc:
        await interaction.followup.send(f"❌ فشل إرسال اختبار الأخبار: {exc}", ephemeral=True)


@bot.tree.command(name="welcome_test", description="اختبار رسالة الترحيب في قناة الترحيب")
async def welcome_test_slash(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
        return
    if not has_staff_access(interaction.user):
        await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة فقط.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    ch = await bot._welcome_channel()
    if not ch:
        await interaction.followup.send(
            f"❌ تعذر الوصول لقناة الترحيب. تحقق من DISCORD_WELCOME_CHANNEL_ID الحالي: `{WELCOME_CHANNEL_ID}`",
            ephemeral=True,
        )
        return
    try:
        embed = bot._build_welcome_embed(interaction.user)
        embed.title = "👋 اختبار الترحيب"
        embed.description = "إذا ظهرت هذه الرسالة فـ قناة الترحيب مضبوطة بشكل صحيح."
        async with bot._discord_call_gate:
            msg = await ch.send(content=f"مرحباً {interaction.user.mention}", embed=embed, view=WelcomeLinksView())
        await interaction.followup.send(
            f"✅ تم إرسال اختبار الترحيب إلى {ch.mention} (message_id={msg.id})",
            ephemeral=True,
        )
    except Exception as exc:
        await interaction.followup.send(f"❌ فشل إرسال اختبار الترحيب: {exc}", ephemeral=True)


@bot.tree.command(name="rank", description="عرض مستواك الحالي")
async def rank_slash(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
        return
    if RANK_CHANNEL_ID > 0 and int(interaction.channel_id or 0) != int(RANK_CHANNEL_ID):
        await interaction.response.send_message(f"❌ استخدم الأمر داخل <#{RANK_CHANNEL_ID}> فقط.", ephemeral=True)
        return

    doc = await bot.db.discord_levels.find_one(
        {"guild_id": interaction.guild.id, "user_id": interaction.user.id},
        {"_id": 0, "xp": 1, "level": 1},
    ) or {"xp": 0, "level": 0}
    mult = bot._vip_xp_multiplier_for_member(interaction.user)
    embed = bot._build_rank_embed(
        interaction.user,
        xp=int(doc.get("xp", 0) or 0),
        level=int(doc.get("level", 0) or 0),
        gained=0,
        multiplier=mult,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.command(name="rank")
async def rank_cmd(ctx: commands.Context):
    if not isinstance(ctx.author, discord.Member) or not ctx.guild:
        await ctx.reply("❌ هذا الأمر داخل السيرفر فقط.", mention_author=False)
        return
    if RANK_CHANNEL_ID > 0 and int(ctx.channel.id) != int(RANK_CHANNEL_ID):
        await ctx.reply(f"❌ استخدم الأمر داخل <#{RANK_CHANNEL_ID}> فقط.", mention_author=False)
        return

    doc = await bot.db.discord_levels.find_one(
        {"guild_id": ctx.guild.id, "user_id": ctx.author.id},
        {"_id": 0, "xp": 1, "level": 1},
    ) or {"xp": 0, "level": 0}
    mult = bot._vip_xp_multiplier_for_member(ctx.author)
    embed = bot._build_rank_embed(
        ctx.author,
        xp=int(doc.get("xp", 0) or 0),
        level=int(doc.get("level", 0) or 0),
        gained=0,
        multiplier=mult,
    )
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="set_level_channel")
async def set_level_channel_cmd(ctx: commands.Context, *, target: str = ""):
    if not isinstance(ctx.author, discord.Member) or not ctx.guild:
        await ctx.reply("❌ هذا الأمر داخل السيرفر فقط.", mention_author=False)
        return
    if not has_staff_access(ctx.author):
        await ctx.reply("❌ هذا الأمر مخصص للإدارة فقط.", mention_author=False)
        return

    raw = (target or "").strip()
    # !set_level_channel default  -> clear explicit channel and fallback to general/system
    if raw.lower() in {"default", "general", "auto"}:
        await bot.db.discord_bot_settings.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"updated_at": iso(now_utc())}, "$unset": {"level_up_channel_id": ""}},
            upsert=True,
        )
        await ctx.reply("✅ تم ضبط قناة التهنئة على الوضع الافتراضي (الشات العام/النظام).", mention_author=False)
        return

    # no target => current channel
    channel: Optional[discord.TextChannel] = None
    if not raw:
        channel = ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None
    else:
        m = re.search(r"(\d{8,25})", raw)
        if m:
            ch = ctx.guild.get_channel(int(m.group(1)))
            if isinstance(ch, discord.TextChannel):
                channel = ch

    if not channel:
        await ctx.reply("❌ حدّد قناة صحيحة أو استخدم: `!set_level_channel default`", mention_author=False)
        return

    await bot.db.discord_bot_settings.update_one(
        {"guild_id": ctx.guild.id},
        {
            "$set": {
                "level_up_channel_id": int(channel.id),
                "updated_by": int(ctx.author.id),
                "updated_at": iso(now_utc()),
            }
        },
        upsert=True,
    )
    await ctx.reply(f"✅ تم تعيين قناة تهنئة التلفيل إلى {channel.mention}", mention_author=False)


@bot.tree.command(name="set_level_role", description="تحديد رتبة تلقائية لمستوى معيّن")
@app_commands.describe(level="رقم المستوى", role="الرتبة التي تُمنح عند هذا المستوى")
async def set_level_role_slash(interaction: discord.Interaction, level: app_commands.Range[int, 1, 500], role: discord.Role):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
        return
    if not has_staff_access(interaction.user):
        await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة فقط.", ephemeral=True)
        return

    await bot.db.discord_level_roles.update_one(
        {"guild_id": interaction.guild.id, "level": int(level)},
        {"$set": {"role_id": int(role.id), "updated_by": int(interaction.user.id), "updated_at": iso(now_utc())}},
        upsert=True,
    )
    await interaction.response.send_message(f"✅ L{int(level)} → {role.mention}", ephemeral=True)


@bot.tree.command(name="add_xp", description="إضافة XP لعضو (إدارة فقط)")
@app_commands.describe(member="العضو المستهدف", amount="كمية XP")
async def add_xp_slash(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 10000]):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
        return
    if not has_staff_access(interaction.user):
        await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة فقط.", ephemeral=True)
        return

    res = await bot._grant_xp(member, int(amount), source="slash:add_xp")
    msg = f"✅ {member.mention} | XP: {res['xp']} | L{res['old_level']} → L{res['new_level']}"
    if res.get("role_granted"):
        msg += " | 🎖️ role granted"
    await interaction.response.send_message(msg, ephemeral=True)


@bot.command(name="hide")
async def hide_cmd(ctx: commands.Context):
    if not isinstance(ctx.author, discord.Member) or not ctx.guild:
        await ctx.reply("❌ هذا الأمر يعمل داخل السيرفر فقط.", mention_author=False)
        return
    msg = await bot.toggle_plus_visibility(ctx.author, ctx.channel, visible=False)
    await ctx.reply(msg, mention_author=False)


@bot.command(name="show")
async def show_cmd(ctx: commands.Context):
    if not isinstance(ctx.author, discord.Member) or not ctx.guild:
        await ctx.reply("❌ هذا الأمر يعمل داخل السيرفر فقط.", mention_author=False)
        return
    msg = await bot.toggle_plus_visibility(ctx.author, ctx.channel, visible=True)
    await ctx.reply(msg, mention_author=False)


@bot.tree.command(name="hide", description="إخفاء روم البلس الخاص بكم")
async def hide_slash(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.channel:
        await interaction.response.send_message("❌ هذا الأمر يعمل داخل السيرفر فقط.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    msg = await bot.toggle_plus_visibility(interaction.user, interaction.channel, visible=False)
    await interaction.followup.send(msg, ephemeral=True)


@bot.tree.command(name="show", description="إظهار روم البلس الخاص بكم")
async def show_slash(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.channel:
        await interaction.response.send_message("❌ هذا الأمر يعمل داخل السيرفر فقط.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    msg = await bot.toggle_plus_visibility(interaction.user, interaction.channel, visible=True)
    await interaction.followup.send(msg, ephemeral=True)


@bot.tree.command(name="tickets_panel", description="نشر لوحة تذاكر الدعم الفني")
async def tickets_panel_slash(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
        return
    if not has_staff_access(interaction.user):
        await interaction.response.send_message("❌ ليس لديك صلاحية نشر لوحة التذاكر.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    view = await bot._build_ticket_panel_view()
    embed = bot.build_ticket_panel_embed()

    await interaction.channel.send(embed=embed, view=view)
    await interaction.followup.send("✅ تم نشر لوحة التذاكر.", ephemeral=True)


ticket_setup_group = app_commands.Group(
    name="ticket_setup",
    description="إدارة أقسام التذاكر من داخل ديسكورد",
)


async def ticket_category_name_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    if not interaction.guild:
        return []

    q = {"guild_id": interaction.guild.id, "is_active": True}
    needle = (current or "").strip()
    if needle:
        q["name"] = {"$regex": re.escape(needle), "$options": "i"}

    try:
        docs = await bot.db.discord_ticket_categories.find(q, {"_id": 0, "name": 1}).sort([
            ("sort_order", 1), ("name", 1)
        ]).to_list(25)
    except Exception:
        return []

    seen = set()
    out: List[app_commands.Choice[str]] = []
    for d in docs:
        nm = (d.get("name") or "").strip()
        if not nm or nm in seen:
            continue
        seen.add(nm)
        out.append(app_commands.Choice(name=nm[:100], value=nm[:100]))
    return out


@ticket_setup_group.command(name="add_category", description="إضافة/تحديث قسم تذاكر بالقائمة المنسدلة")
@app_commands.describe(
    name="اسم القسم (مثال: Rivals Plus)",
    description="وصف القسم",
    emoji_name="اسم الإيموجي المخصص المرفوع بالسيرفر",
    category_id="Discord Category ID الطويل",
    support_role_id="Discord Support Role ID",
)
@app_commands.autocomplete(name=ticket_category_name_autocomplete)
async def ticket_setup_add_category(
    interaction: discord.Interaction,
    name: str,
    description: Optional[str] = None,
    emoji_name: Optional[str] = None,
    category_id: Optional[str] = None,
    support_role_id: Optional[str] = None,
):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
        return

    if not has_staff_access(interaction.user):
        await interaction.response.send_message("❌ ليس لديك صلاحية إدارة إعدادات التذاكر.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    existing = await bot.db.discord_ticket_categories.find_one(
        {
            "guild_id": interaction.guild.id,
            "name": {"$regex": f"^{re.escape((name or '').strip())}$", "$options": "i"},
        },
        {"_id": 0, "id": 1, "name": 1},
    )

    if not existing:
        missing = []
        if description is None:
            missing.append("description")
        if emoji_name is None:
            missing.append("emoji_name")
        if category_id is None:
            missing.append("category_id")
        if support_role_id is None:
            missing.append("support_role_id")
        if missing:
            await interaction.followup.send(
                (
                    "❌ القسم غير موجود. للإضافة الجديدة يرجى تعبئة الحقول الأساسية كاملة:\n"
                    f"{', '.join(missing)}"
                ),
                ephemeral=True,
            )
            return

    parsed_category_id: Optional[int] = None
    if category_id:
        if not str(category_id).isdigit():
            await interaction.followup.send("❌ category_id يجب أن يكون رقمًا صحيحًا.", ephemeral=True)
            return
        parsed_category_id = int(category_id)
        category_obj = interaction.guild.get_channel(parsed_category_id)
        if not isinstance(category_obj, discord.CategoryChannel):
            await interaction.followup.send("❌ لم يتم العثور على Category صحيحة بهذا category_id.", ephemeral=True)
            return

    parsed_support_role_id: Optional[int] = None
    if support_role_id:
        if not str(support_role_id).isdigit():
            await interaction.followup.send("❌ support_role_id يجب أن يكون رقمًا صحيحًا.", ephemeral=True)
            return
        parsed_support_role_id = int(support_role_id)
        role_obj = interaction.guild.get_role(parsed_support_role_id)
        if not role_obj:
            await interaction.followup.send("❌ لم يتم العثور على رتبة صحيحة بهذا support_role_id.", ephemeral=True)
            return

    emoji_literal: Optional[str] = None
    if emoji_name:
        emoji_literal = await bot._resolve_custom_emoji_literal(interaction.guild, emoji_name)
        if not emoji_literal:
            await interaction.followup.send(
                "❌ لم أجد الإيموجي المخصص بهذا الاسم داخل السيرفر. تأكد من emoji_name بدون نقطتين.",
                ephemeral=True,
            )
            return

    try:
        saved = await bot.add_ticket_category(
            guild=interaction.guild,
            name=name,
            description=description,
            emoji_literal=emoji_literal,
            category_id=parsed_category_id,
            support_role_id=parsed_support_role_id,
        )
        updated, failed = await bot.refresh_ticket_panel_messages(interaction.guild)
    except Exception as exc:
        await interaction.followup.send(f"❌ فشل حفظ القسم: {exc}", ephemeral=True)
        return

    saved_category_id = str(saved.get("discord_category_id") or "")
    saved_support_role_id = str(saved.get("support_role_id") or "")
    saved_category_mention = f"<#{saved_category_id}>" if saved_category_id.isdigit() else "—"
    saved_role_mention = f"<@&{saved_support_role_id}>" if saved_support_role_id.isdigit() else "—"

    await interaction.followup.send(
        (
            f"✅ تم حفظ القسم: **{saved.get('name')}**\n"
            f"• Emoji: {saved.get('emoji') or '—'}\n"
            f"• Category: {saved_category_mention}\n"
            f"• Support Role: {saved_role_mention}\n"
            f"• تم تحديث لوحات التذاكر فوراً: {updated} | فشل: {failed}"
        ),
        ephemeral=True,
    )


@ticket_setup_group.command(name="delete_category", description="حذف قسم تذاكر من القائمة")
@app_commands.describe(category_name="اسم القسم المراد حذفه")
@app_commands.autocomplete(category_name=ticket_category_name_autocomplete)
async def ticket_setup_delete_category(
    interaction: discord.Interaction,
    category_name: str,
):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("❌ هذا الأمر داخل السيرفر فقط.", ephemeral=True)
        return

    if not has_staff_access(interaction.user):
        await interaction.response.send_message("❌ ليس لديك صلاحية إدارة إعدادات التذاكر.", ephemeral=True)
        return

    target_name = (category_name or "").strip()
    if not target_name:
        await interaction.response.send_message("❌ يجب تحديد اسم القسم المراد حذفه.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        match = await bot.db.discord_ticket_categories.find_one(
            {
                "guild_id": interaction.guild.id,
                "name": {"$regex": f"^{re.escape(target_name)}$", "$options": "i"},
            },
            {"_id": 0, "id": 1, "name": 1},
        )
        if not match:
            await interaction.followup.send("❌ لم يتم العثور على قسم بهذا الاسم.", ephemeral=True)
            return

        deleted = await bot.db.discord_ticket_categories.delete_many(
            {
                "guild_id": interaction.guild.id,
                "name": {"$regex": f"^{re.escape(match.get('name', target_name))}$", "$options": "i"},
            }
        )

        updated, failed = await bot.refresh_ticket_panel_messages(interaction.guild)
    except Exception as exc:
        await interaction.followup.send(f"❌ فشل حذف القسم: {exc}", ephemeral=True)
        return

    await interaction.followup.send(
        (
            f"✅ تم حذف القسم: **{match.get('name', target_name)}**\n"
            f"• عدد السجلات المحذوفة: {deleted.deleted_count}\n"
            f"• تم تحديث لوحات التذاكر فوراً: {updated} | فشل: {failed}"
        ),
        ephemeral=True,
    )


bot.tree.add_command(ticket_setup_group)


if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is required")
    bot.run(DISCORD_BOT_TOKEN)
