from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
# Load .env from backend dir first, then fall back to repo root
load_dotenv(ROOT_DIR / '.env', override=False)
load_dotenv(ROOT_DIR.parent / '.env', override=False)

import os
import re
import uuid
import string
import asyncio
import logging
import secrets
import smtplib
import base64
import io
import time
import json
import ipaddress
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Any
from urllib.parse import urlparse, urlencode
from urllib.request import urlopen, Request as UrlRequest
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText

from PIL import Image as PILImage

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, Query, Form, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pydantic import BaseModel, Field, EmailStr

# ---------------- Setup ----------------
mongo_url = (
    os.environ.get('MONGO_URI')
    or os.environ.get('MONGO_URL')
    or "mongodb://localhost:27017"
)
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'rivals')]

JWT_SECRET = (os.environ.get("JWT_SECRET") or "").strip()
JWT_SECRET_IS_EPHEMERAL = False
if not JWT_SECRET:
    # Secure per-process fallback for local/dev only when env is missing.
    JWT_SECRET = base64.urlsafe_b64encode(os.urandom(48)).decode()
    JWT_SECRET_IS_EPHEMERAL = True
JWT_ALG = "HS256"
ACCESS_MIN = 60 * 24
REFRESH_DAYS = 30

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
OTP_TTL_MINUTES = int((os.environ.get("OTP_TTL_MINUTES") or "10").strip() or 10)
OTP_MAX_ATTEMPTS = int((os.environ.get("OTP_MAX_ATTEMPTS") or "5").strip() or 5)
ONE_ACCOUNT_PER_IP_ENABLED = (os.environ.get("ONE_ACCOUNT_PER_IP_ENABLED") or "true").strip().lower() not in {"0", "false", "no", "off"}
ANTI_VPN_BLOCK_ENABLED = (os.environ.get("ANTI_VPN_BLOCK_ENABLED") or "true").strip().lower() not in {"0", "false", "no", "off"}
PRAYER_ALERT_WINDOW_SECONDS = 15 * 60
GUARD_HEARTBEAT_STALE_SECONDS = 90
GUARD_ALERT_MAX_BYTES = 24 * 1024 * 1024
REFERRAL_REWARD_RIV_POINTS = 1
RIV_COST_PERSON_PLUS = 11
RIV_COST_CLAN_PLUS = 27

NOTIFICATION_TYPE_GENERAL = "general"
NOTIFICATION_TYPE_CLAN_INVITE = "clan_invite"
NOTIFICATION_TYPE_CLAN_CHALLENGE = "clan_challenge"
NOTIFICATION_ACTIONABLE_TYPES = {NOTIFICATION_TYPE_CLAN_INVITE, NOTIFICATION_TYPE_CLAN_CHALLENGE}
ATTENDANCE_RETENTION_ALERT_TEXT = "🎮 وينك عن اخوياك؟ كلانك ياولد بدأ يحضر للبطولة و محتاجين نجمهم ادخل الصفحة واضغط زر التحضير ولا تخليهم يلعبون ناقصين.🏆"
ATTENDANCE_RETENTION_INACTIVE_HOURS = 72
ATTENDANCE_RETENTION_COOLDOWN_HOURS = 24

app = FastAPI(title="Rivals Esports API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rivals")

if JWT_SECRET_IS_EPHEMERAL:
    logger.warning("JWT_SECRET is not set in environment. Using ephemeral runtime secret (tokens reset after restart).")

_SERVICE_STARTED_AT = datetime.now(timezone.utc)
_metrics_route_counts = defaultdict(int)
_metrics_status_counts = defaultdict(int)
_metrics_rate_limited_by_scope = defaultdict(int)
_metrics_global = {
    "requests_total": 0,
    "errors_total": 0,
    "rate_limited_total": 0,
}
_rate_limit_store: dict[str, list[float]] = {}
_prayer_time_cache: dict[str, dict] = {}


@app.middleware("http")
async def request_metrics_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    route = request.url.path
    try:
        response = await call_next(request)
    except Exception:
        _metrics_global["requests_total"] += 1
        _metrics_global["errors_total"] += 1
        _metrics_route_counts[route] += 1
        _metrics_status_counts["500"] += 1
        raise
    _metrics_global["requests_total"] += 1
    _metrics_route_counts[route] += 1
    _metrics_status_counts[str(response.status_code)] += 1
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    return response

BAN_BLOCK_MESSAGE = "حسابك محظور من المنصة لمدة سنة كاملة بسبب إدراجك في القائمة السوداء."


# ---------------- Helpers ----------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def _client_ip(request: Request) -> str:
    xf = request.headers.get("x-forwarded-for", "")
    if xf:
        return xf.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_public_ip(ip: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address((ip or "").strip())
        return not (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_reserved
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_unspecified
        )
    except Exception:
        return False


def _fetch_ip_profile_sync(ip: str) -> dict:
    # Uses ip-api.com free endpoint for coarse geolocation + proxy/hosting flags.
    # For non-public/local IPs, returns a safe local profile and no block signal.
    if not _is_public_ip(ip):
        return {
            "ip": ip,
            "city": "",
            "region": "",
            "country": "",
            "proxy": False,
            "hosting": False,
            "mobile": False,
            "vpn_blocked": False,
            "source": "local",
        }
    fields = "status,message,country,regionName,city,proxy,hosting,mobile,query"
    url = f"http://ip-api.com/json/{ip}?fields={fields}"
    req = UrlRequest(url, headers={"User-Agent": "rivals-security/1.0"})
    with urlopen(req, timeout=3.5) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    ok = (payload or {}).get("status") == "success"
    city = (payload.get("city") or "").strip() if ok else ""
    region = (payload.get("regionName") or "").strip() if ok else ""
    country = (payload.get("country") or "").strip() if ok else ""
    proxy = bool(payload.get("proxy")) if ok else False
    hosting = bool(payload.get("hosting")) if ok else False
    mobile = bool(payload.get("mobile")) if ok else False
    vpn_blocked = bool(proxy or hosting)
    return {
        "ip": ip,
        "city": city,
        "region": region,
        "country": country,
        "proxy": proxy,
        "hosting": hosting,
        "mobile": mobile,
        "vpn_blocked": vpn_blocked,
        "source": "ip-api",
    }


async def _resolve_ip_profile(ip: str) -> dict:
    try:
        return await asyncio.to_thread(_fetch_ip_profile_sync, ip)
    except Exception as exc:
        logger.warning("IP profile lookup failed for %s: %s", ip, exc)
        return {
            "ip": ip,
            "city": "",
            "region": "",
            "country": "",
            "proxy": False,
            "hosting": False,
            "mobile": False,
            "vpn_blocked": False,
            "source": "fallback",
        }


def _prayer_name_ar(name_en: str) -> str:
    m = {
        "Fajr": "الفجر",
        "Dhuhr": "الظهر",
        "Asr": "العصر",
        "Maghrib": "المغرب",
        "Isha": "العشاء",
    }
    return m.get(name_en, name_en)


def _fetch_prayer_snapshot_sync(city: str, country: str) -> Optional[dict]:
    city = (city or "").strip()
    country = (country or "").strip() or "Saudi Arabia"
    if not city:
        return None
    key = f"{city.lower()}::{country.lower()}"
    cached = _prayer_time_cache.get(key)
    if cached and cached.get("expires_at") and cached["expires_at"] > time.time():
        return cached.get("data")

    params = urlencode({"city": city, "country": country, "method": 4})
    req = UrlRequest(
        f"https://api.aladhan.com/v1/timingsByCity?{params}",
        headers={"User-Agent": "rivals-prayer/1.0"},
    )
    with urlopen(req, timeout=4.0) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    data = (payload or {}).get("data") or {}
    timings = data.get("timings") or {}
    tz = ((data.get("meta") or {}).get("timezone") or "Asia/Riyadh").strip()
    out = {
        "city": city,
        "country": country,
        "timezone": tz,
        "timings": {k: str(v).split(" ")[0] for k, v in timings.items()},
        "fetched_at": iso(now_utc()),
    }
    _prayer_time_cache[key] = {"data": out, "expires_at": time.time() + 60 * 30}
    return out


async def _fetch_prayer_snapshot(city: str, country: str) -> Optional[dict]:
    try:
        return await asyncio.to_thread(_fetch_prayer_snapshot_sync, city, country)
    except Exception as exc:
        logger.warning("Prayer API lookup failed for %s/%s: %s", city, country, exc)
        return None


def _rate_limit_or_429(request: Request, scope: str, limit: int, window_seconds: int) -> None:
    now_ts = time.time()
    bucket_key = f"{scope}:{_client_ip(request)}"
    history = _rate_limit_store.get(bucket_key, [])
    cutoff = now_ts - window_seconds
    history = [ts for ts in history if ts >= cutoff]
    if len(history) >= limit:
        _metrics_global["rate_limited_total"] += 1
        _metrics_rate_limited_by_scope[scope] += 1
        raise HTTPException(429, "تم تجاوز الحد المسموح من الطلبات، حاول لاحقاً")
    history.append(now_ts)
    _rate_limit_store[bucket_key] = history


def _smtp_config() -> dict:
    host = (
        (os.environ.get("SMTP_HOST") or "").strip()
        or (os.environ.get("EMAIL_HOST") or "").strip()
        or (os.environ.get("EMAIL_SMTP_HOST") or "").strip()
        or (os.environ.get("GMAIL_SMTP_HOST") or "").strip()
        or "smtp.gmail.com"
    )
    port_raw = (
        (os.environ.get("SMTP_PORT") or "").strip()
        or (os.environ.get("EMAIL_PORT") or "").strip()
        or (os.environ.get("EMAIL_SMTP_PORT") or "").strip()
        or (os.environ.get("GMAIL_SMTP_PORT") or "").strip()
        or "587"
    )
    try:
        port = int(port_raw)
    except Exception:
        port = 587

    username = (
        (os.environ.get("SMTP_USERNAME") or "").strip()
        or (os.environ.get("SMTP_USER") or "").strip()
        or (os.environ.get("EMAIL_USER") or "").strip()
        or (os.environ.get("EMAIL_SMTP_USER") or "").strip()
        or (os.environ.get("GMAIL_SMTP_USER") or "").strip()
        or (os.environ.get("GMAIL_EMAIL") or "").strip()
    )
    password = (
        (os.environ.get("SMTP_PASSWORD") or "").strip()
        or (os.environ.get("SMTP_PASS") or "").strip()
        or (os.environ.get("EMAIL_PASSWORD") or "").strip()
        or (os.environ.get("EMAIL_PASS") or "").strip()
        or (os.environ.get("EMAIL_SMTP_PASS") or "").strip()
        or (os.environ.get("GMAIL_SMTP_PASS") or "").strip()
        or (os.environ.get("GMAIL_APP_PASSWORD") or "").strip()
    )
    from_email = (
        (os.environ.get("SMTP_FROM") or "").strip()
        or (os.environ.get("EMAIL_FROM") or "").strip()
        or username
        or (os.environ.get("OWNER_EMAIL") or "").strip()
    )
    use_starttls_raw = (os.environ.get("SMTP_USE_STARTTLS") or "true").strip().lower()
    if not (os.environ.get("SMTP_USE_STARTTLS") or "").strip():
        use_starttls_raw = (os.environ.get("EMAIL_USE_STARTTLS") or use_starttls_raw).strip().lower()
    use_starttls = use_starttls_raw not in {"0", "false", "no", "off"}
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "from_email": from_email,
        "use_starttls": use_starttls,
    }


def _smtp_is_configured(cfg: dict) -> bool:
    return bool(cfg.get("host") and cfg.get("username") and cfg.get("password") and cfg.get("from_email"))


def _mask_email(email: str) -> str:
    e = (email or "").strip()
    if "@" not in e:
        return "***"
    name, domain = e.split("@", 1)
    if len(name) <= 2:
        return f"{name[:1]}***@{domain}"
    return f"{name[:2]}***{name[-1]}@{domain}"


def _otp_label(purpose: str) -> str:
    labels = {
        "register": "تأكيد إنشاء الحساب",
        "login": "تأكيد تسجيل الدخول",
        "reset_password": "إعادة تعيين كلمة المرور",
    }
    return labels.get(purpose, "تأكيد الهوية")


def _send_email_sync(to_email: str, subject: str, body: str) -> None:
    cfg = _smtp_config()
    if not _smtp_is_configured(cfg):
        raise RuntimeError("SMTP is not configured")

    msg = MIMEText(body, _subtype="plain", _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg["from_email"]
    msg["To"] = to_email

    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
        if cfg.get("use_starttls"):
            server.starttls()
        server.login(cfg["username"], cfg["password"])
        server.sendmail(cfg["from_email"], [to_email], msg.as_string())


async def _send_otp_email(to_email: str, purpose: str, code: str) -> None:
    label = _otp_label(purpose)
    subject = f"RIVALS OTP - {label}"
    body = (
        f"رمز التحقق الخاص بك: {code}\n"
        f"الاستخدام: {label}\n"
        f"صلاحية الرمز: {OTP_TTL_MINUTES} دقائق\n\n"
        "إذا لم تطلب هذا الرمز، تجاهل الرسالة."
    )
    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, body)
    except Exception as exc:
        logger.error("Failed to send OTP email to %s: %s", to_email, exc)
        raise HTTPException(500, "تعذر إرسال رمز التحقق عبر البريد")


async def _create_email_otp(purpose: str, email: str, payload: Optional[dict] = None, user_id: str = "") -> dict:
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = now_utc()

    await db.email_otps.update_many(
        {"purpose": purpose, "email": email, "status": "pending"},
        {"$set": {"status": "replaced", "updated_at": iso(now)}},
    )

    doc = {
        "id": str(uuid.uuid4()),
        "purpose": purpose,
        "email": email,
        "user_id": user_id,
        "payload": payload or {},
        "code_hash": hash_pw(code),
        "attempts": 0,
        "status": "pending",
        "created_at": iso(now),
        "updated_at": iso(now),
        "expires_at": iso(now + timedelta(minutes=max(1, OTP_TTL_MINUTES))),
        "used_at": None,
    }
    await db.email_otps.insert_one(doc)
    await _send_otp_email(email, purpose, code)
    return doc


async def _verify_email_otp(purpose: str, email: str, otp: str, user_id: str = "") -> dict:
    doc = await db.email_otps.find_one(
        {"purpose": purpose, "email": email, "status": "pending"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not doc:
        raise HTTPException(400, "رمز التحقق غير صالح")

    if user_id and (doc.get("user_id") or "") and doc.get("user_id") != user_id:
        raise HTTPException(400, "رمز التحقق غير صالح")

    try:
        if datetime.fromisoformat(doc.get("expires_at", "")) <= now_utc():
            await db.email_otps.update_one(
                {"id": doc["id"]},
                {"$set": {"status": "expired", "updated_at": iso(now_utc())}},
            )
            raise HTTPException(400, "انتهت صلاحية رمز التحقق")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "رمز التحقق غير صالح")

    if int(doc.get("attempts") or 0) >= max(1, OTP_MAX_ATTEMPTS):
        await db.email_otps.update_one(
            {"id": doc["id"]},
            {"$set": {"status": "blocked", "updated_at": iso(now_utc())}},
        )
        raise HTTPException(400, "تم تجاوز عدد المحاولات المسموح")

    if not verify_pw((otp or "").strip(), doc.get("code_hash") or ""):
        attempts = int(doc.get("attempts") or 0) + 1
        status = "blocked" if attempts >= max(1, OTP_MAX_ATTEMPTS) else "pending"
        await db.email_otps.update_one(
            {"id": doc["id"]},
            {"$set": {"attempts": attempts, "status": status, "updated_at": iso(now_utc())}},
        )
        raise HTTPException(400, "رمز التحقق غير صحيح")

    await db.email_otps.update_one(
        {"id": doc["id"]},
        {"$set": {"status": "verified", "used_at": iso(now_utc()), "updated_at": iso(now_utc())}},
    )
    return doc


async def _create_notification(
    user_id: str,
    title: str,
    body: str,
    kind: str = "system",
    sender_id: str = "",
    n_type: str = NOTIFICATION_TYPE_GENERAL,
    status: str = "pending",
    message: Optional[str] = None,
    data: Optional[dict] = None,
) -> dict:
    now_iso = iso(now_utc())
    clean_sender = (sender_id or "").strip()
    clean_type = (n_type or NOTIFICATION_TYPE_GENERAL).strip()
    clean_status = (status or "pending").strip() or "pending"
    clean_message = (message if isinstance(message, str) and message.strip() else body)[:1200]
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "sender_id": clean_sender,
        "type": clean_type,
        "status": clean_status,
        "message": clean_message,
        "kind": kind,
        "title": title[:180],
        "body": body[:1200],
        "data": data or {},
        "read_at": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.notifications.insert_one(doc)
    return doc


async def _generate_unique_referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(30):
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        if not await db.users.find_one({"referral_code": code}, {"_id": 0, "id": 1}):
            return code
    return f"RIV{uuid.uuid4().hex[:9].upper()}"


async def _resolve_referrer_from_code(code: str) -> Optional[dict]:
    clean = (code or "").strip().upper()
    if not clean:
        return None
    return await db.users.find_one({"referral_code": clean}, {"_id": 0, "id": 1, "username": 1})


def _safe_iso_to_dt(raw: Optional[str], fallback: datetime) -> datetime:
    if not raw:
        return fallback
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return fallback


async def _extend_person_plus_for_user(user_id: str, months: int = 1) -> Optional[str]:
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "personal_plus_until": 1, "premium_until": 1})
    if not user:
        return None
    now = now_utc()
    person_base = max(now, _safe_iso_to_dt(user.get("personal_plus_until"), now))
    premium_base = max(now, _safe_iso_to_dt(user.get("premium_until"), now))
    new_personal = person_base + timedelta(days=30 * max(1, months))
    new_premium = premium_base + timedelta(days=30 * max(1, months))
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"personal_plus_until": iso(new_personal), "premium_until": iso(new_premium)}},
    )
    return iso(new_personal)


async def _extend_clan_plus_for_user(user_id: str, months: int = 1) -> Optional[str]:
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "plus_expires_at": 1, "premium_until": 1})
    if not user:
        return None
    now = now_utc()
    plus_base = max(now, _safe_iso_to_dt(user.get("plus_expires_at"), now))
    premium_base = max(now, _safe_iso_to_dt(user.get("premium_until"), now))
    new_plus = plus_base + timedelta(days=30 * max(1, months))
    new_premium = premium_base + timedelta(days=30 * max(1, months))
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"plus_expires_at": iso(new_plus), "premium_until": iso(new_premium)}},
    )
    return iso(new_plus)


def _is_actionable_notification(n: dict) -> bool:
    n_type = (n.get("type") or "").strip()
    status = (n.get("status") or "").strip().lower()
    return n_type in NOTIFICATION_ACTIONABLE_TYPES and status == "pending"


def _normalize_notification(n: dict) -> dict:
    n_type = (n.get("type") or NOTIFICATION_TYPE_GENERAL).strip() or NOTIFICATION_TYPE_GENERAL
    message = (n.get("message") or n.get("body") or "").strip()
    status = (n.get("status") or "pending").strip() or "pending"
    if n.get("read_at") and status == "pending" and n_type not in NOTIFICATION_ACTIONABLE_TYPES:
        status = "read"
    channel = "actionable" if _is_actionable_notification({**n, "status": status, "type": n_type}) else "general"
    out = {
        **n,
        "type": n_type,
        "status": status,
        "message": message,
        "channel": channel,
        "actionable": channel == "actionable",
    }
    out.pop("_id", None)
    return out


async def _send_attendance_retention_alerts() -> int:
    now = now_utc()
    stale_before = now - timedelta(hours=ATTENDANCE_RETENTION_INACTIVE_HOURS)
    sent = 0
    async for u in db.users.find(
        {"clan_id": {"$nin": [None, ""]}},
        {"_id": 0, "id": 1, "clan_id": 1},
    ):
        user_id = (u.get("id") or "").strip()
        clan_id = (u.get("clan_id") or "").strip()
        if not user_id or not clan_id:
            continue

        att_doc = await db.clan_attendance.find_one(
            {"clan_id": clan_id},
            {"_id": 0, "last_interaction_at": 1},
        )
        last_map = (att_doc or {}).get("last_interaction_at") or {}
        last_raw = (last_map.get(user_id) or "").strip()

        last_dt = None
        if last_raw:
            try:
                last_dt = datetime.fromisoformat(last_raw)
            except Exception:
                last_dt = None
        if last_dt and last_dt > stale_before:
            continue

        recent_cutoff = iso(now - timedelta(hours=ATTENDANCE_RETENTION_COOLDOWN_HOURS))
        recent = await db.notifications.find_one(
            {
                "user_id": user_id,
                "kind": "attendance_retention",
                "created_at": {"$gte": recent_cutoff},
            },
            {"_id": 0, "id": 1},
        )
        if recent:
            continue

        await _create_notification(
            user_id=user_id,
            sender_id=clan_id,
            n_type=NOTIFICATION_TYPE_GENERAL,
            status="pending",
            kind="attendance_retention",
            title="تذكير التحضير",
            body=ATTENDANCE_RETENTION_ALERT_TEXT,
            message=ATTENDANCE_RETENTION_ALERT_TEXT,
            data={
                "route": f"/clans/{clan_id}?highlight_checkin=1",
                "highlight": "checkin",
            },
        )
        sent += 1
    if sent:
        logger.info("Attendance retention alerts sent: %s", sent)
    return sent


async def _attendance_retention_loop() -> None:
    while True:
        try:
            await _send_attendance_retention_alerts()
        except Exception as exc:
            logger.error("Attendance retention loop error: %s", exc)
        await asyncio.sleep(24 * 3600)


async def _audit_admin_action(
    actor: dict,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    meta: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    if not actor or actor.get("role") not in ("admin", "owner"):
        return
    ip = _client_ip(request) if request else None
    ua = (request.headers.get("user-agent", "")[:240] if request else "")
    doc = {
        "id": str(uuid.uuid4()),
        "actor_id": actor.get("id"),
        "actor_username": actor.get("username"),
        "actor_role": actor.get("role"),
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "meta": meta or {},
        "ip": ip,
        "user_agent": ua,
        "created_at": iso(now_utc()),
    }
    try:
        await db.audit_log.insert_one(doc)
    except Exception as exc:
        logger.warning(f"Audit log insert failed: {exc}")


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def make_token(user_id: str, email: str, role: str, session_id: Optional[str] = None) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "exp": now_utc() + timedelta(minutes=ACCESS_MIN),
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def make_refresh_token(user_id: str, session_id: str) -> str:
    return jwt.encode({
        "sub": user_id,
        "sid": session_id,
        "type": "refresh",
        "exp": now_utc() + timedelta(days=REFRESH_DAYS),
    }, JWT_SECRET, algorithm=JWT_ALG)


def _extract_token_from_request(request: Request, cookie_name: str = "access_token") -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        bearer = auth[7:].strip()
        if bearer and bearer.lower() not in {"undefined", "null", "none"}:
            return bearer
    token = (request.cookies.get(cookie_name) or "").strip()
    if token and token.lower() not in {"undefined", "null", "none"}:
        return token
    return None


def _decode_jwt_or_401(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


def _request_client_meta(request: Request) -> tuple[Optional[str], str]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:240]
    return ip, ua


async def _create_auth_session(user_id: str, request: Request) -> dict:
    sid = str(uuid.uuid4())
    ip, ua = _request_client_meta(request)
    created = now_utc()
    session = {
        "id": sid,
        "user_id": user_id,
        "created_at": iso(created),
        "last_seen_at": iso(created),
        "expires_at": iso(created + timedelta(days=REFRESH_DAYS)),
        "revoked_at": None,
        "revoked_reason": None,
        "ip": ip,
        "user_agent": ua,
    }
    await db.auth_sessions.insert_one(session)
    return session


async def _revoke_session(session_id: str, reason: str = "user_logout") -> None:
    await db.auth_sessions.update_one(
        {"id": session_id, "revoked_at": None},
        {"$set": {"revoked_at": iso(now_utc()), "revoked_reason": reason}},
    )


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
    attendances = u.get("attendances", 0)
    mvp_count = u.get("mvp_count", 0)
    return {
        "id": u["id"],
        "email": u["email"],
        "username": u["username"],
        "act": u.get("act", ""),
        "gaming_platform": u.get("gaming_platform", "pc"),
        "act_changed_at": u.get("act_changed_at"),
        "role": u.get("role", "player"),
        "discord_id": u.get("discord_id"),
        "discord_username": u.get("discord_username", ""),
        "clan_id": u.get("clan_id"),
        "points": u.get("points", 0),
        "wins": wins,
        "losses": losses,
        "attendances": attendances,
        "mvp_count": mvp_count,
        "kd": compute_kd(wins, losses),
        "avatar": u.get("avatar"),
        "banner": u.get("banner"),
        "accent_color": u.get("accent_color"),
        "is_plus": user_is_plus(u),
        "is_personal_plus": user_is_personal_plus(u),
        "isPlusSubscriber": user_is_plus_subscriber(u),
        "referral_code": u.get("referral_code", ""),
        "riv_points": int(u.get("riv_points", 0) or 0),
        "premium_until": u.get("premium_until"),
        "personal_plus_until": u.get("personal_plus_until"),
        "plus_expires_at": u.get("plus_expires_at"),
        "clan_cooldown_until": u.get("clan_cooldown_until"),
        "twitch_url": u.get("twitch_url", ""),
        "kick_url": u.get("kick_url", ""),
        "youtube_url": u.get("youtube_url", ""),
        "tiktok_url": u.get("tiktok_url", ""),
        "instagram_link": u.get("instagram_link", ""),
        "x_link": u.get("x_link", ""),
        "last_seen_at": last_seen,
        "is_online": is_online,
        "prayer_break_cooldown_until": u.get("prayer_break_cooldown_until"),
        "status": u.get("status", "Active"),
        "banned_until": u.get("banned_until"),
        "banned_at": u.get("banned_at"),
        "created_at": u.get("created_at"),
    }


def _one_year_later(dt: datetime) -> datetime:
    try:
        return dt.replace(year=dt.year + 1)
    except ValueError:
        # Handles leap-day edge case
        return dt + timedelta(days=365)


async def _enforce_ban_guard(user: dict) -> None:
    """Block access for currently banned users; auto-clear expired bans."""
    if (user.get("status") or "").lower() != "banned":
        return
    banned_until_iso = user.get("banned_until")
    if not banned_until_iso:
        raise HTTPException(403, BAN_BLOCK_MESSAGE)
    try:
        banned_until = datetime.fromisoformat(banned_until_iso)
    except Exception:
        raise HTTPException(403, BAN_BLOCK_MESSAGE)

    if banned_until > now_utc():
        raise HTTPException(403, BAN_BLOCK_MESSAGE)

    # Ban expired -> unlock account automatically
    await db.users.update_one(
        {"id": user["id"]},
        {
            "$set": {"status": "Active"},
            "$unset": {
                "banned_until": "",
                "banned_at": "",
                "ban_reason": "",
            },
        },
    )


def _assert_act_set(user: dict) -> None:
    """Block clan join attempts when player's Activision ID is missing."""
    if not (user.get("act") or "").strip():
        raise HTTPException(400, "يجب حفظ Activision ID في الملف الشخصي قبل الانضمام لكلان")


def _clan_suspension_remaining_seconds(clan: dict) -> int:
    until_iso = clan.get("suspended_until")
    if not until_iso:
        return 0
    try:
        until_dt = datetime.fromisoformat(until_iso)
    except Exception:
        return 0
    return max(0, int((until_dt - now_utc()).total_seconds()))


def _format_remaining_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h <= 0:
        return f"{max(1, m)} دقيقة"
    if m <= 0:
        return f"{h} ساعة"
    return f"{h} ساعة و{m} دقيقة"


def user_is_plus_subscriber(u: dict) -> bool:
    return bool(user_is_plus(u) or user_is_personal_plus(u))


def _humanize_duration(start_iso: Optional[str], end_iso: Optional[str]) -> str:
    if not start_iso or not end_iso:
        return "مدة غير متوفرة"
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
    except Exception:
        return "مدة غير متوفرة"
    if end <= start:
        return "أقل من يوم"
    total_days = (end - start).days
    months = total_days // 30
    days = total_days % 30
    if months > 0 and days > 0:
        return f"{months} شهر و {days} يوم"
    if months > 0:
        return f"{months} شهر"
    return f"{max(1, days)} يوم"


async def _create_news_post(kind: str, title: str, body: str = "", payload: Optional[dict] = None,
                            created_by: str = "system", created_by_role: str = "system") -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "title": title,
        "body": body or "",
        "payload": payload or {},
        "created_by": created_by,
        "created_by_role": created_by_role,
        "created_at": iso(now_utc()),
        "discord_status": "queued",
        "discord_updated_at": iso(now_utc()),
    }
    await db.news_posts.insert_one(doc)
    try:
        await _enqueue_discord_job(
            "news_post",
            {
                "news_id": doc["id"],
                "kind": doc["kind"],
                "title": doc["title"],
                "body": doc["body"],
                "payload": doc["payload"],
            },
            dedupe_key=f"news_post:{doc['id']}",
            priority=30,
        )
    except Exception as exc:
        logger.warning("Discord enqueue failed (news_post:%s): %s", doc["id"], exc)
    doc.pop("_id", None)
    return doc


async def _record_transfer_market_event(user_doc: dict, old_clan_id: str, new_clan_id: str,
                                        old_joined_at: Optional[str], old_left_at: Optional[str]) -> None:
    if not old_clan_id or not new_clan_id or old_clan_id == new_clan_id:
        return
    old_clan = await db.clans.find_one({"id": old_clan_id}, {"_id": 0, "id": 1, "name": 1, "tag": 1, "logo": 1})
    new_clan = await db.clans.find_one({"id": new_clan_id}, {"_id": 0, "id": 1, "name": 1, "tag": 1, "logo": 1})
    duration_label = _humanize_duration(old_joined_at, old_left_at)
    event = {
        "id": str(uuid.uuid4()),
        "user_id": user_doc["id"],
        "username": user_doc.get("username", ""),
        "old_clan": old_clan,
        "new_clan": new_clan,
        "old_joined_at": old_joined_at,
        "old_left_at": old_left_at,
        "duration_label": duration_label,
        "created_at": iso(now_utc()),
    }
    await db.transfer_events.insert_one(event)
    await _create_news_post(
        kind="transfer_market",
        title=f"انتقال جديد: {user_doc.get('username', '')}",
        body=f"انتقل اللاعب من {((old_clan or {}).get('name') or 'كلان سابق')} إلى {((new_clan or {}).get('name') or 'كلان جديد')} — قضى {duration_label}",
        payload=event,
    )


async def _resolve_avatar_render_for_user(user_doc: dict) -> dict:
    profile = sanitize_user(user_doc)
    avatar_creator = user_doc.get("avatar_creator")
    if not avatar_creator:
        profile["avatar_render"] = None
        return profile
    render = {
        "gender": avatar_creator.get("gender"),
        "layers": avatar_creator.get("layers", {}),
        "body_frame": avatar_creator.get("body_frame"),
        "style_preset": avatar_creator.get("style_preset"),
    }
    profile["avatar_render"] = render
    return profile


def _assert_clan_not_suspended(clan: dict) -> None:
    remaining = _clan_suspension_remaining_seconds(clan)
    if remaining > 0:
        reason = (clan.get("suspension_reason") or "").strip()
        extra = f" السبب: {reason}." if reason else ""
        raise HTTPException(
            400,
            f"الكلان موقوف مؤقتاً ولا يمكنه التسجيل حالياً. المتبقي {_format_remaining_duration(remaining)}.{extra}",
        )


MIN_CLAN_MEMBERS_FOR_COMPETITION = 6
COMPETITION_MIN_MEMBERS_MSG = "لا يمكنك المشاركة في الدوري إلا بعد وصول عدد أعضاء الكلان إلى 6 لاعبين على الأقل."
PLUS_TRIAL_MIN_MEMBERS_MSG = "يجب أن يحتوي الكلان على 6 لاعبين على الأقل لتفعيل التجربة المجانية"


async def _active_clan_members_count(clan: dict) -> int:
    clan_id = clan.get("id")
    if not clan_id:
        return 0
    return await db.users.count_documents({"clan_id": clan_id})


async def _assert_min_members_for_competitions(clan: dict) -> int:
    members_count = await _active_clan_members_count(clan)
    if members_count < MIN_CLAN_MEMBERS_FOR_COMPETITION:
        raise HTTPException(400, COMPETITION_MIN_MEMBERS_MSG)
    return members_count


def _assert_clan_can_match(clan: dict) -> None:
    """Roster minimum gate for issuing/accepting matches."""
    if clan.get("archived"):
        raise HTTPException(400, "هذا الكلان مؤرشف")
    _assert_clan_not_suspended(clan)
    members = len(clan.get("member_ids", []))
    if members < CHALLENGE_MIN_MEMBERS:
        raise HTTPException(400, f"الكلان يحتاج {CHALLENGE_MIN_MEMBERS} لاعبين على الأقل لخوض المباريات ({members}/{CHALLENGE_MIN_MEMBERS})")


CLAN_LEAVE_COOLDOWN_HOURS = 3


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
    current = await db.users.find_one({"id": user_id}, {"_id": 0, "clan_id": 1, "clan_joined_at": 1})
    until = iso(now_utc() + timedelta(hours=CLAN_LEAVE_COOLDOWN_HOURS))
    leave_at = iso(now_utc())
    old_clan_id = (current or {}).get("clan_id")
    old_joined_at = (current or {}).get("clan_joined_at")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "clan_id": None,
            "clan_cooldown_until": until,
            "last_clan_id": old_clan_id,
            "last_clan_joined_at": old_joined_at,
            "last_clan_left_at": leave_at,
            "clan_joined_at": None,
        }},
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
    token = _extract_token_from_request(request, "access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = _decode_jwt_or_401(token)
    token_type = payload.get("type")
    if token_type and token_type != "access":
        raise HTTPException(401, "Invalid token type")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(401, "User not found")

    sid = payload.get("sid")
    if sid:
        sess = await db.auth_sessions.find_one({"id": sid, "user_id": user["id"]}, {"_id": 0})
        if not sess or sess.get("revoked_at"):
            raise HTTPException(401, "Session revoked")
        try:
            if datetime.fromisoformat(sess.get("expires_at", "")) <= now_utc():
                raise HTTPException(401, "Session expired")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(401, "Session invalid")

    await _enforce_ban_guard(user)
    # Record presence (used for online-clan filtering)
    try:
        await db.users.update_one({"id": user["id"]}, {"$set": {"last_seen_at": iso(now_utc())}})
        if sid:
            await db.auth_sessions.update_one(
                {"id": sid},
                {"$set": {"last_seen_at": iso(now_utc())}},
            )
    except Exception:
        pass
    return user


def _cookie_flags() -> tuple[bool, str]:
    env_name = (os.environ.get("APP_ENV") or os.environ.get("ENV") or "development").strip().lower()
    force_secure = (os.environ.get("AUTH_COOKIE_SECURE") or "").strip().lower()
    if force_secure in {"1", "true", "yes", "on"}:
        secure = True
    elif force_secure in {"0", "false", "no", "off"}:
        secure = False
    else:
        secure = env_name in {"production", "prod", "staging"}
    same_site = "none" if secure else "lax"
    return secure, same_site


def set_auth_cookie(resp: Response, token: str):
    secure, same_site = _cookie_flags()
    resp.set_cookie(
        "access_token", token,
        httponly=True, secure=secure, samesite=same_site,
        max_age=ACCESS_MIN * 60, path="/",
    )


def set_refresh_cookie(resp: Response, token: str):
    secure, same_site = _cookie_flags()
    resp.set_cookie(
        "refresh_token", token,
        httponly=True, secure=secure, samesite=same_site,
        max_age=REFRESH_DAYS * 24 * 60 * 60, path="/",
    )


def clear_auth_cookies(resp: Response):
    resp.delete_cookie("access_token", path="/")
    resp.delete_cookie("refresh_token", path="/")


# ---------------- Models ----------------
class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=30)
    password: str = Field(min_length=6, max_length=128)
    act: str = Field(min_length=2, max_length=40)  # In-game COD name
    accepted_terms: bool = False
    otp: Optional[str] = None
    referral_code: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    otp: Optional[str] = None
    csrf_token: Optional[str] = None
    recaptcha_token: Optional[str] = None
    cf_turnstile_response: Optional[str] = None


class ResetPasswordIn(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=6, max_length=128)


class AuthRevokeIn(BaseModel):
    session_id: Optional[str] = None


class BillingCheckoutIn(BaseModel):
    plan: Literal["plus_monthly", "plus_yearly", "person_plus", "clan_plus"] = "plus_monthly"
    provider: Optional[Literal["stripe", "myfatoorah", "manual", "riv_points"]] = "stripe"
    success_url: Optional[str] = ""
    cancel_url: Optional[str] = ""
    pay_with_riv_points: bool = False


class BillingWebhookIn(BaseModel):
    provider: Optional[str] = ""
    event_type: Optional[str] = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationReadIn(BaseModel):
    ids: List[str] = Field(default_factory=list)
    mark_all: bool = False


class ClanCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    tag: str = Field(min_length=2, max_length=8)
    description: Optional[str] = ""


class InviteIn(BaseModel):
    user_id: str


class ContractOfferIn(BaseModel):
    user_id: str
    terms: Optional[str] = ""


class HandleRequestIn(BaseModel):
    action: Literal["accept", "reject"]


class MatchCreateIn(BaseModel):
    clan_a_id: str
    clan_b_id: str
    notes: Optional[str] = ""
    league_id: Optional[str] = None


class ChallengeIn(BaseModel):
    opponent_clan_id: str
    notes: Optional[str] = ""
    league_id: Optional[str] = None


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


class MvpVoteIn(BaseModel):
    player_id: str


class RuleIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    body: str = Field(min_length=1)
    order: int = 0
    image: Optional[str] = ""  # base64 data URL or external link
    images: List[str] = Field(default_factory=list)  # multi images (data URLs or external links)


class ProfileUpdateIn(BaseModel):
    gaming_platform: Optional[Literal["pc", "ps5", "xbox", "console"]] = None
    discord_username: Optional[str] = None
    twitch_url: Optional[str] = ""
    kick_url: Optional[str] = ""
    youtube_url: Optional[str] = ""
    tiktok_url: Optional[str] = ""
    instagram_link: Optional[str] = ""
    x_link: Optional[str] = ""
    act: Optional[str] = None
    avatar: Optional[str] = None        # base64 data URL (≤2MB) — Personal Plus only
    banner: Optional[str] = None        # base64 data URL (≤3MB) — Personal Plus only
    accent_color: Optional[str] = None  # hex string — Personal Plus only


class AvatarCreatorIn(BaseModel):
    gender: Literal["male", "female"]
    layers: dict[str, str] = Field(default_factory=dict)
    body_frame: Optional[str] = ""
    style_preset: Optional[str] = ""


class ClanLogoUpdateIn(BaseModel):
    logo: str = Field(min_length=8)


class NewsCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    body: Optional[str] = ""
    kind: Optional[str] = "admin"


class NewsUpdateIn(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=160)
    body: Optional[str] = None


class AdminUserEditIn(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
    act: Optional[str] = None


class AdminClanEditIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=40)
    tag: Optional[str] = Field(default=None, min_length=2, max_length=8)
    description: Optional[str] = None


class GuardConnectIn(BaseModel):
    match_id: str
    platform: Optional[Literal["pc", "ps5", "xbox", "console"]] = "pc"
    session_token: Optional[str] = None
    app_version: Optional[str] = ""
    hwid_hash: Optional[str] = ""


class GuardHeartbeatIn(BaseModel):
    match_id: str
    session_token: Optional[str] = None


class GuardHwidBanIn(BaseModel):
    hwid_hash: str = Field(min_length=8, max_length=200)
    reason: Optional[str] = ""


class ClanSuspendIn(BaseModel):
    hours: int = Field(ge=1, le=24 * 365)
    reason: Optional[str] = ""


class DiscordLinkIn(BaseModel):
    discord_id: str = Field(min_length=4, max_length=40)


class DiscordClanRoleCreateIn(BaseModel):
    clan_id: str = Field(min_length=4, max_length=64)


class DiscordClanRoleSyncMemberIn(BaseModel):
    user_id: str = Field(min_length=4, max_length=64)
    old_clan_id: Optional[str] = ""
    new_clan_id: Optional[str] = ""


class DiscordPlusChannelsCreateIn(BaseModel):
    clan_id: str = Field(min_length=4, max_length=64)


class DiscordModerationSyncIn(BaseModel):
    user_id: str = Field(min_length=4, max_length=64)
    action: Literal["warn", "timeout", "ban", "unban", "remove_timeout"]
    reason: Optional[str] = ""
    until: Optional[str] = ""
    warning_points: Optional[int] = 0


class DiscordTicketCreateIn(BaseModel):
    user_id: str = Field(min_length=4, max_length=64)
    subject: Optional[str] = ""
    message: Optional[str] = ""


class DiscordTicketCategoryUpsertIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = ""
    emoji: Optional[str] = ""
    discord_category_id: str = Field(min_length=3, max_length=40)
    support_role_id: str = Field(min_length=3, max_length=40)
    is_active: Optional[bool] = True
    sort_order: Optional[int] = 100


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class BlacklistIn(BaseModel):
    player_name: str = Field(min_length=2, max_length=80)
    player_user_id: Optional[str] = None
    player_email: Optional[str] = ""
    cheat_tool: str = Field(min_length=1, max_length=120)
    details: Optional[str] = ""
    proof_image: Optional[str] = ""  # base64 data URL or upload URL


class CustomLeagueIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    game: str = Field(default="Call of Duty", min_length=2, max_length=40)
    rules: Optional[str] = ""
    description: Optional[str] = ""
    rules_image: Optional[str] = ""  # primary banner image (data URL or http)
    super_rivals_enabled: bool = False


class CustomLeagueUpdateIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    game: Optional[str] = Field(default=None, min_length=2, max_length=40)
    rules: Optional[str] = None
    description: Optional[str] = None
    rules_image: Optional[str] = None  # primary banner image (data URL or http)
    super_rivals_enabled: Optional[bool] = None
    status: Optional[Literal["active", "finished", "completed"]] = None


class LeagueStatusUpdateIn(BaseModel):
    status: Literal["active", "finished", "completed"]


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


async def _cleanup_removed_clan_customization_fields() -> None:
    """One-time migration: remove deprecated clan design fields."""
    try:
        await db.clans.update_many({}, {"$unset": {"jersey": ""}})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Clan customization cleanup skipped: %s", exc)


async def _ensure_referral_fields_for_existing_users() -> None:
    await db.users.update_many(
        {"riv_points": {"$exists": False}},
        {"$set": {"riv_points": 0}},
    )
    await db.users.update_many(
        {"premium_until": {"$exists": False}},
        {"$set": {"premium_until": None}},
    )
    cursor = db.users.find(
        {
            "$or": [
                {"referral_code": {"$exists": False}},
                {"referral_code": None},
                {"referral_code": ""},
            ]
        },
        {"_id": 0, "id": 1},
    )
    async for u in cursor:
        code = await _generate_unique_referral_code()
        await db.users.update_one({"id": u["id"]}, {"$set": {"referral_code": code}})


@app.on_event("startup")
async def startup() -> None:
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username")
    await db.users.create_index("registration_ip")
    await db.users.create_index([("registration_city", 1), ("registration_country", 1)])
    await db.clans.create_index("name", unique=True)
    await db.clans.create_index("tag", unique=True)
    await db.matches.create_index("status")
    await db.chat_messages.create_index("match_id")
    await db.join_requests.create_index([("clan_id", 1), ("user_id", 1)])
    await db.rules.create_index("order")
    await db.news_posts.create_index("created_at")
    await db.transfer_events.create_index("created_at")
    await db.transfer_events.create_index("user_id")
    await db.auth_sessions.create_index("id", unique=True)
    await db.auth_sessions.create_index([("user_id", 1), ("created_at", -1)])
    await db.billing_subscriptions.create_index([("user_id", 1), ("status", 1)])
    await db.billing_events.create_index([("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("read_at", 1)])
    await db.notifications.create_index([("user_id", 1), ("type", 1), ("status", 1), ("created_at", -1)])
    await db.notifications.create_index([("kind", 1), ("created_at", -1)])
    await db.referrals.create_index([("referred_id", 1)], unique=True)
    await db.referrals.create_index([("referrer_id", 1), ("created_at", -1)])
    await db.system_jobs.create_index([("job", 1), ("period", 1)], unique=True)
    await db.audit_log.create_index([("created_at", -1)])
    await db.audit_log.create_index([("actor_id", 1), ("created_at", -1)])
    await db.discord_ticket_categories.create_index("id", unique=True)
    await db.discord_ticket_categories.create_index([("guild_id", 1), ("is_active", 1), ("sort_order", 1), ("name", 1)])
    await db.discord_tickets.create_index("id", unique=True)
    await db.discord_tickets.create_index([("guild_id", 1), ("channel_id", 1)], unique=True)
    await db.discord_tickets.create_index([("guild_id", 1), ("creator_discord_id", 1), ("status", 1), ("created_at", -1)])
    await db.email_otps.create_index([("purpose", 1), ("email", 1), ("status", 1), ("created_at", -1)])
    await db.email_otps.create_index([("expires_at", 1)])
    await db.sanad_questions.create_index([("created_at", -1)])
    await db.sanad_questions.create_index([("match_id", 1), ("created_at", -1)])
    await db.guard_sessions.create_index([("match_id", 1), ("user_id", 1)], unique=True)
    await db.guard_sessions.create_index([("last_seen_at", -1)])
    await db.guard_alerts.create_index([("match_id", 1), ("created_at", -1)])
    await db.guard_alerts.create_index([("created_at", -1)])
    await db.guard_hwid_bans.create_index([("hwid_hash", 1)], unique=True)

    await db.users.update_many(
        {"gaming_platform": {"$exists": False}},
        {"$set": {"gaming_platform": "pc"}},
    )

    await _cleanup_removed_clan_customization_fields()
    await _ensure_referral_fields_for_existing_users()

    # Seed admin/owner from env only (no insecure hardcoded defaults)
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    admin_pw = os.environ.get("ADMIN_PASSWORD") or ""
    if admin_email and admin_pw:
        existing = await db.users.find_one({"email": admin_email})
        if not existing:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": admin_email,
                "username": "Admin",
                "password_hash": hash_pw(admin_pw),
                "referral_code": await _generate_unique_referral_code(),
                "riv_points": 0,
                "premium_until": None,
                "role": "admin",
                "points": 0,
                "clan_id": None,
                "avatar": None,
                "is_plus": True,
                "created_at": iso(now_utc()),
            })
            logger.info(f"Seeded admin from env: {admin_email}")
        elif not verify_pw(admin_pw, existing["password_hash"]):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": hash_pw(admin_pw), "role": "admin"}}
            )
    else:
        logger.warning("ADMIN_EMAIL/ADMIN_PASSWORD are not fully configured. Skipping admin seed.")

    owner_email = (os.environ.get("OWNER_EMAIL") or "").strip().lower()
    owner_pw = os.environ.get("OWNER_PASSWORD") or ""
    owner_username = (os.environ.get("OWNER_USERNAME") or "").strip() or (owner_email.split("@")[0] if owner_email else "Owner")
    if owner_email and owner_pw:
        existing_owner = await db.users.find_one({"email": owner_email})
        if not existing_owner:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": owner_email,
                "username": owner_username,
                "password_hash": hash_pw(owner_pw),
                "referral_code": await _generate_unique_referral_code(),
                "riv_points": 0,
                "premium_until": None,
                "role": "owner",
                "points": 0,
                "clan_id": None,
                "avatar": None,
                "is_plus": True,
                "created_at": iso(now_utc()),
            })
            logger.info(f"Seeded owner from env: {owner_email}")
        elif existing_owner.get("role") != "owner":
            await db.users.update_one({"email": owner_email}, {"$set": {"role": "owner"}})
    else:
        logger.warning("OWNER_EMAIL/OWNER_PASSWORD are not fully configured. Skipping owner seed.")

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

    # Write local helper file only when admin seed is configured.
    if admin_email and admin_pw:
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
    # Start daily retention reminders for clan attendance inactivity
    asyncio.create_task(_attendance_retention_loop())
    # Start monthly hall-of-fame evaluator (runs at last day 23:59)
    asyncio.create_task(_monthly_hall_of_fame_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    client.close()


# ---------------- AUTH ----------------
@api.post("/auth/register")
async def register(body: RegisterIn, request: Request, response: Response):
    _rate_limit_or_429(request, "auth:register", limit=8, window_seconds=15 * 60)
    if not body.accepted_terms:
        raise HTTPException(400, "يجب الموافقة على الشروط والأحكام وسياسة الخصوصية قبل التسجيل")
    email = body.email.lower()
    referral_code = (
        (request.query_params.get("ref") or "").strip()
        or (body.referral_code or "").strip()
    ).upper()
    current_ip = _client_ip(request)
    ip_profile = await _resolve_ip_profile(current_ip)

    if ANTI_VPN_BLOCK_ENABLED and ip_profile.get("vpn_blocked"):
        raise HTTPException(400, "عذراً، لا يُسمح باستخدام VPN/Proxy أثناء التسجيل.")

    if ONE_ACCOUNT_PER_IP_ENABLED and _is_public_ip(current_ip):
        existing_on_ip = await db.users.find_one(
            {"registration_ip": current_ip},
            {"_id": 0, "id": 1},
        )
        if existing_on_ip:
            raise HTTPException(400, "عذراً، يُسمح بإنشاء حساب واحد فقط لكل شبكة/جهاز!")
    if not (body.otp or "").strip():
        if await db.users.find_one({"email": email}):
            raise HTTPException(400, "البريد مسجل من قبل")
        if await db.users.find_one({"username": body.username}):
            raise HTTPException(400, "اسم المستخدم محجوز")

        valid_referral_code = ""
        if referral_code:
            referrer = await _resolve_referrer_from_code(referral_code)
            if referrer:
                valid_referral_code = referral_code

        await _create_email_otp(
            purpose="register",
            email=email,
            payload={
                "username": body.username,
                "act": body.act.strip(),
                "password_hash": hash_pw(body.password),
                "accepted_terms": True,
                "referral_code": valid_referral_code,
            },
        )
        return {
            "ok": True,
            "otp_required": True,
            "message": "تم إرسال رمز التحقق إلى بريدك الإلكتروني",
            "email_hint": _mask_email(email),
        }

    otp_doc = await _verify_email_otp("register", email, body.otp or "")
    payload = otp_doc.get("payload") or {}
    username = (payload.get("username") or body.username or "").strip()
    act = (payload.get("act") or body.act or "").strip()
    password_hash = (payload.get("password_hash") or "").strip()
    referral_code = ((payload.get("referral_code") or referral_code or "").strip() or "").upper()

    if not username or not act or not password_hash:
        raise HTTPException(400, "بيانات التسجيل غير مكتملة، أعد طلب رمز جديد")
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "البريد مسجل من قبل")
    if await db.users.find_one({"username": username}):
        raise HTTPException(400, "اسم المستخدم محجوز")

    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "username": username,
        "act": act,
        "gaming_platform": "pc",
        "password_hash": password_hash,
        "referral_code": await _generate_unique_referral_code(),
        "riv_points": 0,
        "premium_until": None,
        "role": "player",
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
        "personal_plus_until": iso(now_utc() + timedelta(days=PERSONAL_PLUS_TRIAL_DAYS)),
        "clan_cooldown_until": None,
        "email_verified_at": iso(now_utc()),
        "registration_ip": current_ip,
        "registration_city": ip_profile.get("city", ""),
        "registration_region": ip_profile.get("region", ""),
        "registration_country": ip_profile.get("country", ""),
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(user)

    if referral_code:
        referrer = await db.users.find_one(
            {"referral_code": referral_code},
            {"_id": 0, "id": 1, "username": 1, "registration_ip": 1},
        )
        if referrer and referrer.get("id") != user["id"]:
            referrer_ip = (referrer.get("registration_ip") or "").strip()
            ip_conflict = bool(current_ip and referrer_ip and current_ip == referrer_ip)
            if ip_conflict:
                logger.warning("Referral blocked by anti-cheat (same IP): referrer=%s referred=%s ip=%s", referrer.get("id"), user["id"], current_ip)

            existing_ref = await db.referrals.find_one({"referred_id": user["id"]}, {"_id": 0, "id": 1})
            if (not existing_ref) and (not ip_conflict) and user.get("email_verified_at"):
                await db.referrals.insert_one({
                    "id": str(uuid.uuid4()),
                    "referrer_id": referrer["id"],
                    "referred_id": user["id"],
                    "referred_ip": current_ip,
                    "created_at": iso(now_utc()),
                })
                await db.users.update_one(
                    {"id": referrer["id"]},
                    {"$inc": {"riv_points": REFERRAL_REWARD_RIV_POINTS}},
                )
                await _create_notification(
                    user_id=referrer["id"],
                    sender_id=user["id"],
                    n_type=NOTIFICATION_TYPE_GENERAL,
                    status="pending",
                    kind="referral_reward",
                    title="مكافأة دعوة جديدة",
                    body=f"تمت دعوتك بنجاح! حصلت على +{REFERRAL_REWARD_RIV_POINTS} RIV.",
                    message=f"تمت دعوتك بنجاح! حصلت على +{REFERRAL_REWARD_RIV_POINTS} RIV.",
                    data={"route": "/me"},
                )

    session = await _create_auth_session(user["id"], request)
    token = make_token(user["id"], user["email"], user["role"], session_id=session["id"])
    refresh_token = make_refresh_token(user["id"], session["id"])
    set_auth_cookie(response, token)
    set_refresh_cookie(response, refresh_token)
    return {
        "user": await _resolve_avatar_render_for_user(user),
        "token": token,
        "refresh_token": refresh_token,
        "session_id": session["id"],
    }


@api.post("/auth/login")
async def login(body: LoginIn, request: Request, response: Response):
    _rate_limit_or_429(request, "auth:login", limit=20, window_seconds=15 * 60)
    # Optional security token compatibility (CSRF / reCAPTCHA / Cloudflare Turnstile)
    security_token = (
        (body.cf_turnstile_response or "").strip()
        or (body.recaptcha_token or "").strip()
        or (body.csrf_token or "").strip()
        or (request.headers.get("CF-Turnstile-Response") or "").strip()
        or (request.headers.get("X-Recaptcha-Token") or "").strip()
        or (request.headers.get("X-CSRF-Token") or "").strip()
    )
    if security_token:
        # Hook reserved for future verification/provider validation without breaking existing clients.
        pass
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_pw(body.password, user["password_hash"]):
        raise HTTPException(401, "البريد أو كلمة المرور غير صحيحة")
    await _enforce_ban_guard(user)

    if not (body.otp or "").strip():
        await _create_email_otp(
            purpose="login",
            email=email,
            payload={"user_id": user["id"]},
            user_id=user["id"],
        )
        return {
            "ok": True,
            "otp_required": True,
            "message": "تم إرسال رمز تحقق لتأكيد تسجيل الدخول",
            "email_hint": _mask_email(email),
        }

    await _verify_email_otp("login", email, body.otp or "", user_id=user["id"])

    session = await _create_auth_session(user["id"], request)
    token = make_token(user["id"], user["email"], user["role"], session_id=session["id"])
    refresh_token = make_refresh_token(user["id"], session["id"])
    set_auth_cookie(response, token)
    set_refresh_cookie(response, refresh_token)
    return {
        "user": await _resolve_avatar_render_for_user(user),
        "token": token,
        "refresh_token": refresh_token,
        "session_id": session["id"],
    }


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = _extract_token_from_request(request, "access_token")
    if token:
        try:
            payload = _decode_jwt_or_401(token)
            sid = payload.get("sid")
            if sid:
                await _revoke_session(sid, reason="logout")
        except HTTPException:
            pass
    clear_auth_cookies(response)
    return {"ok": True}


@api.post("/auth/refresh")
async def auth_refresh(request: Request, response: Response):
    refresh_token = _extract_token_from_request(request, "refresh_token")
    if not refresh_token:
        raise HTTPException(401, "Refresh token missing")
    payload = _decode_jwt_or_401(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid token type")

    user_id = payload.get("sub")
    sid = payload.get("sid")
    if not user_id or not sid:
        raise HTTPException(401, "Invalid refresh token")

    session = await db.auth_sessions.find_one({"id": sid, "user_id": user_id}, {"_id": 0})
    if not session or session.get("revoked_at"):
        raise HTTPException(401, "Session revoked")
    try:
        if datetime.fromisoformat(session.get("expires_at", "")) <= now_utc():
            await _revoke_session(sid, reason="refresh_expired")
            raise HTTPException(401, "Session expired")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Session invalid")

    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        await _revoke_session(sid, reason="user_missing")
        raise HTTPException(401, "User not found")
    await _enforce_ban_guard(user)

    await db.auth_sessions.update_one({"id": sid}, {"$set": {"last_seen_at": iso(now_utc())}})

    new_access = make_token(user["id"], user["email"], user["role"], session_id=sid)
    new_refresh = make_refresh_token(user["id"], sid)
    set_auth_cookie(response, new_access)
    set_refresh_cookie(response, new_refresh)
    return {
        "ok": True,
        "token": new_access,
        "refresh_token": new_refresh,
        "user": await _resolve_avatar_render_for_user(user),
    }


@api.post("/auth/revoke")
async def auth_revoke(body: AuthRevokeIn, request: Request, response: Response, user: dict = Depends(get_current_user)):
    target_sid = (body.session_id or "").strip()
    if not target_sid:
        token = _extract_token_from_request(request, "access_token")
        if token:
            try:
                payload = _decode_jwt_or_401(token)
                target_sid = payload.get("sid") or ""
            except HTTPException:
                target_sid = ""

    if target_sid:
        await db.auth_sessions.update_one(
            {"id": target_sid, "user_id": user["id"], "revoked_at": None},
            {"$set": {"revoked_at": iso(now_utc()), "revoked_reason": "user_revoke"}},
        )
    clear_auth_cookies(response)
    return {"ok": True, "revoked_session_id": target_sid or None}


@api.get("/auth/sessions")
async def auth_sessions(request: Request, user: dict = Depends(get_current_user)):
    current_sid = None
    token = _extract_token_from_request(request, "access_token")
    if token:
        try:
            payload = _decode_jwt_or_401(token)
            current_sid = payload.get("sid")
        except HTTPException:
            current_sid = None

    docs = await db.auth_sessions.find(
        {"user_id": user["id"], "revoked_at": None},
        {"_id": 0},
    ).sort("created_at", -1).to_list(30)

    now = now_utc()
    sessions = []
    for s in docs:
        expired = False
        try:
            expired = datetime.fromisoformat(s.get("expires_at", "")) <= now
        except Exception:
            expired = True
        sessions.append({
            "id": s.get("id"),
            "created_at": s.get("created_at"),
            "last_seen_at": s.get("last_seen_at"),
            "expires_at": s.get("expires_at"),
            "ip": s.get("ip"),
            "user_agent": s.get("user_agent"),
            "is_current": s.get("id") == current_sid,
            "is_expired": expired,
        })
    return sessions


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return await _resolve_avatar_render_for_user(user)


@api.get("/me/referrals")
async def my_referrals(user: dict = Depends(get_current_user)):
    referral_code = (user.get("referral_code") or "").strip()
    if not referral_code:
        referral_code = await _generate_unique_referral_code()
        await db.users.update_one({"id": user["id"]}, {"$set": {"referral_code": referral_code}})
    invited_count = await db.referrals.count_documents({"referrer_id": user["id"]})
    base_url = (os.environ.get("PUBLIC_APP_URL") or "https://rivalsesports.games").rstrip("/")
    referral_link = f"{base_url}/auth?ref={referral_code}"
    return {
        "referral_code": referral_code,
        "referral_link": referral_link,
        "riv_points": int(user.get("riv_points", 0) or 0),
        "invited_count": int(invited_count),
        "reward_per_invite": REFERRAL_REWARD_RIV_POINTS,
    }


@api.post("/me/plus")
async def toggle_plus(user: dict = Depends(get_current_user)):
    """Toggle Plus subscription (free during preview)."""
    new_val = not user.get("is_plus", False)
    if new_val:
        clan_id = user.get("clan_id")
        clan = await db.clans.find_one({"id": clan_id}, {"_id": 0}) if clan_id else None
        members_count = await _active_clan_members_count(clan) if clan else 0
        if members_count < MIN_CLAN_MEMBERS_FOR_COMPETITION:
            raise HTTPException(400, PLUS_TRIAL_MIN_MEMBERS_MSG)
    await db.users.update_one({"id": user["id"]}, {"$set": {"is_plus": new_val}})
    return {"is_plus": new_val}


@api.get("/billing/subscription")
async def billing_subscription_status(user: dict = Depends(get_current_user)):
    """Unified subscription status.
    Keeps admin/owner manual Plus activation fully compatible with future paid billing."""
    now_iso = iso(now_utc())
    billing_sub = await db.billing_subscriptions.find_one(
        {
            "user_id": user["id"],
            "status": "active",
            "$or": [
                {"ends_at": None},
                {"ends_at": ""},
                {"ends_at": {"$gt": now_iso}},
            ],
        },
        {"_id": 0},
        sort=[("created_at", -1)],
    )

    manual_plus_active = bool(user_is_plus(user) or user_is_personal_plus(user))
    billing_plus_active = bool(billing_sub)
    effective_plus = bool(manual_plus_active or billing_plus_active)

    sources = []
    if manual_plus_active:
        sources.append("manual")
    if billing_plus_active:
        sources.append("billing")

    return {
        "user_id": user["id"],
        "is_plus": effective_plus,
        "manual_plus_active": manual_plus_active,
        "billing_plus_active": billing_plus_active,
        "sources": sources,
        "manual": {
            "is_plus": bool(user.get("is_plus")),
            "plus_expires_at": user.get("plus_expires_at"),
            "personal_plus_until": user.get("personal_plus_until"),
        },
        "billing": billing_sub,
    }


@api.post("/billing/checkout")
async def billing_checkout_stub(body: BillingCheckoutIn, user: dict = Depends(get_current_user)):
    """Checkout endpoint.
    - Supports gateway intent stubs (legacy behavior)
    - Supports RIV points purchases for Person Plus / Clan Plus
    """
    use_riv_points = bool(body.pay_with_riv_points or body.provider == "riv_points")
    if use_riv_points:
        if body.plan not in ("person_plus", "clan_plus"):
            raise HTTPException(400, "الدفع بالنقاط متاح فقط لباقات Person Plus و Clan Plus")

        cost = RIV_COST_PERSON_PLUS if body.plan == "person_plus" else RIV_COST_CLAN_PLUS
        balance = int(user.get("riv_points", 0) or 0)
        if balance < cost:
            raise HTTPException(400, "رصيد RIV غير كافٍ")

        new_expiry = None
        if body.plan == "person_plus":
            new_expiry = await _extend_person_plus_for_user(user["id"], months=1)
        else:
            new_expiry = await _extend_clan_plus_for_user(user["id"], months=1)

        await db.users.update_one({"id": user["id"]}, {"$inc": {"riv_points": -cost}})

        event = {
            "id": str(uuid.uuid4()),
            "type": "riv_points_checkout",
            "user_id": user["id"],
            "plan": body.plan,
            "provider": "riv_points",
            "status": "paid",
            "riv_cost": cost,
            "created_at": iso(now_utc()),
        }
        await db.billing_events.insert_one(event)

        fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "riv_points": 1, "personal_plus_until": 1, "plus_expires_at": 1, "premium_until": 1})
        return {
            "ok": True,
            "provider": "riv_points",
            "status": "paid",
            "plan": body.plan,
            "riv_cost": cost,
            "riv_points": int((fresh or {}).get("riv_points", 0) or 0),
            "new_expiry": new_expiry,
            "premium_until": (fresh or {}).get("premium_until"),
            "personal_plus_until": (fresh or {}).get("personal_plus_until"),
            "plus_expires_at": (fresh or {}).get("plus_expires_at"),
        }

    # Legacy checkout intent stub for gateway integrations
    checkout_id = str(uuid.uuid4())
    intent = {
        "id": checkout_id,
        "user_id": user["id"],
        "plan": body.plan,
        "provider": body.provider,
        "status": "pending",
        "success_url": body.success_url or "",
        "cancel_url": body.cancel_url or "",
        "created_at": iso(now_utc()),
    }
    await db.billing_events.insert_one({**intent, "type": "checkout_intent"})
    return {
        "ok": True,
        "checkout_id": checkout_id,
        "status": "pending",
        "provider": body.provider,
        "message": "Checkout stub created. Gateway integration not enabled yet.",
    }


@api.post("/billing/webhook")
async def billing_webhook_stub(body: BillingWebhookIn, request: Request):
    """Stub webhook receiver. Stores incoming events for audit/debug until provider integration is wired."""
    event_doc = {
        "id": str(uuid.uuid4()),
        "type": "webhook",
        "provider": body.provider or "unknown",
        "event_type": body.event_type or "unknown",
        "payload": body.payload or {},
        "headers": {
            "x-signature": request.headers.get("x-signature", ""),
            "x-provider": request.headers.get("x-provider", ""),
        },
        "created_at": iso(now_utc()),
    }
    await db.billing_events.insert_one(event_doc)
    return {"ok": True}


@api.get("/notifications")
async def list_notifications(
    tab: str = "all",
    unread_only: bool = False,
    limit: int = 40,
    user: dict = Depends(get_current_user),
):
    safe_limit = max(1, min(limit, 200))
    query = {"user_id": user["id"]}
    if unread_only:
        query["read_at"] = None
    tab_clean = (tab or "all").strip().lower()
    if tab_clean == "actionable":
        query["type"] = {"$in": list(NOTIFICATION_ACTIONABLE_TYPES)}
    elif tab_clean == "general":
        query["type"] = {"$nin": list(NOTIFICATION_ACTIONABLE_TYPES)}
    docs = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).to_list(safe_limit)
    unread_count = await db.notifications.count_documents({"user_id": user["id"], "read_at": None})
    items = [_normalize_notification(d) for d in docs]
    return {
        "items": items,
        "unread_count": unread_count,
    }


@api.post("/notifications/read")
async def mark_notifications_read(body: NotificationReadIn, user: dict = Depends(get_current_user)):
    now_iso = iso(now_utc())
    if body.mark_all:
        res = await db.notifications.update_many(
            {"user_id": user["id"], "read_at": None},
            {"$set": {"read_at": now_iso, "updated_at": now_iso}},
        )
        await db.notifications.update_many(
            {
                "user_id": user["id"],
                "read_at": {"$ne": None},
                "type": {"$nin": list(NOTIFICATION_ACTIONABLE_TYPES)},
                "status": "pending",
            },
            {"$set": {"status": "read", "updated_at": now_iso}},
        )
        unread_count = await db.notifications.count_documents({"user_id": user["id"], "read_at": None})
        return {"ok": True, "updated": int(res.modified_count), "unread_count": unread_count}

    ids = [x for x in body.ids if isinstance(x, str) and x.strip()]
    if not ids:
        raise HTTPException(400, "يرجى إرسال ids أو mark_all=true")

    res = await db.notifications.update_many(
        {"user_id": user["id"], "id": {"$in": ids}, "read_at": None},
        {"$set": {"read_at": now_iso, "updated_at": now_iso}},
    )
    await db.notifications.update_many(
        {
            "user_id": user["id"],
            "id": {"$in": ids},
            "type": {"$nin": list(NOTIFICATION_ACTIONABLE_TYPES)},
            "status": "pending",
            "read_at": {"$ne": None},
        },
        {"$set": {"status": "read", "updated_at": now_iso}},
    )
    unread_count = await db.notifications.count_documents({"user_id": user["id"], "read_at": None})
    return {"ok": True, "updated": int(res.modified_count), "unread_count": unread_count}


@api.get("/admin/audit-log")
async def admin_audit_log(
    actor_id: str = "",
    action: str = "",
    target_type: str = "",
    limit: int = 200,
    user: dict = Depends(get_current_user),
):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")

    query = {}
    if actor_id.strip():
        query["actor_id"] = actor_id.strip()
    if action.strip():
        query["action"] = action.strip()
    if target_type.strip():
        query["target_type"] = target_type.strip()

    safe_limit = max(1, min(limit, 500))
    docs = await db.audit_log.find(query, {"_id": 0}).sort("created_at", -1).to_list(safe_limit)
    return docs


@api.get("/metrics")
async def api_metrics(user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    uptime_seconds = int((now_utc() - _SERVICE_STARTED_AT).total_seconds())
    return {
        "ok": True,
        "uptime_seconds": uptime_seconds,
        "started_at": iso(_SERVICE_STARTED_AT),
        "totals": dict(_metrics_global),
        "routes": dict(_metrics_route_counts),
        "statuses": dict(_metrics_status_counts),
        "rate_limited_by_scope": dict(_metrics_rate_limited_by_scope),
    }


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
    return await _resolve_avatar_render_for_user(u)


@api.get("/avatar-creator/assets")
async def avatar_creator_assets(gender: Literal["male", "female"] = "male"):
    male = {
        "face_shapes": ["m_face_01", "m_face_02", "m_face_03"],
        "hair": ["m_hair_fade", "m_hair_curl", "m_hair_long"],
        "eyes": ["m_eyes_sharp", "m_eyes_soft", "m_eyes_blue"],
        "facial_structures": ["m_jaw_wide", "m_jaw_narrow", "m_nose_straight"],
        "body_frames": ["athletic", "stocky", "lean"],
    }
    female = {
        "face_shapes": ["f_face_01", "f_face_02", "f_face_03"],
        "hair": ["f_hair_wavy", "f_hair_bun", "f_hair_long"],
        "eyes": ["f_eyes_sharp", "f_eyes_soft", "f_eyes_hazel"],
        "facial_structures": ["f_jaw_soft", "f_cheek_defined", "f_nose_refined"],
        "body_frames": ["athletic", "slim", "curvy"],
    }
    return {"gender": gender, "assets": male if gender == "male" else female}


@api.get("/me/avatar-creator")
async def my_avatar_creator(user: dict = Depends(get_current_user)):
    if not user_is_plus_subscriber(user):
        raise HTTPException(403, "ميزة اصنع شكل اللاعب متاحة لمشتركي Plus فقط")
    return user.get("avatar_creator") or {
        "gender": "male",
        "layers": {},
        "body_frame": "athletic",
        "style_preset": "",
    }


@api.put("/me/avatar-creator")
async def save_my_avatar_creator(body: AvatarCreatorIn, user: dict = Depends(get_current_user)):
    if not user_is_plus_subscriber(user):
        raise HTTPException(403, "ميزة اصنع شكل اللاعب متاحة لمشتركي Plus فقط")
    payload = body.model_dump()
    payload["updated_at"] = iso(now_utc())
    await db.users.update_one({"id": user["id"]}, {"$set": {"avatar_creator": payload}})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return await _resolve_avatar_render_for_user(fresh)


@api.get("/news")
async def list_news(limit: int = 50):
    n = max(1, min(200, int(limit or 50)))
    docs = await db.news_posts.find({}, {"_id": 0}).sort("created_at", -1).to_list(n)
    return docs


@api.post("/news")
async def create_news(body: NewsCreateIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    kind = (body.kind or "admin").strip() or "admin"
    return await _create_news_post(
        kind=kind,
        title=body.title.strip(),
        body=(body.body or "").strip(),
        created_by=user["id"],
        created_by_role=user.get("role", "admin"),
    )


@api.put("/news/{news_id}")
async def update_news(news_id: str, body: NewsUpdateIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    existing = await db.news_posts.find_one({"id": news_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "الخبر غير موجود")
    update: dict[str, Any] = {"updated_at": iso(now_utc()), "updated_by": user["id"]}
    if body.title is not None:
        update["title"] = body.title.strip()
    if body.body is not None:
        update["body"] = body.body.strip()
    await db.news_posts.update_one({"id": news_id}, {"$set": update})
    fresh = await db.news_posts.find_one({"id": news_id}, {"_id": 0})
    return fresh


@api.delete("/news/{news_id}")
async def delete_news(news_id: str, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    result = await db.news_posts.delete_one({"id": news_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "الخبر غير موجود")
    return {"ok": True}


@api.get("/transfers")
async def list_transfer_market(limit: int = 50):
    n = max(1, min(200, int(limit or 50)))
    docs = await db.transfer_events.find({}, {"_id": 0}).sort("created_at", -1).to_list(n)
    return docs


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


async def _get_clan_attendance_doc(clan_id: str) -> dict:
    doc = await db.clan_attendance.find_one({"clan_id": clan_id}, {"_id": 0})
    if doc:
        return doc
    return {
        "clan_id": clan_id,
        "checked_in_ids": [],
        "updated_at": iso(now_utc()),
    }


def _attendance_member_ids(clan: dict, checked_in_ids: list) -> list:
    members = set(clan.get("member_ids", []))
    return [uid for uid in checked_in_ids if uid in members]


async def _clan_attendance_summary(clan: dict) -> dict:
    doc = await _get_clan_attendance_doc(clan["id"])
    checked = _attendance_member_ids(clan, doc.get("checked_in_ids", []))
    count = len(checked)
    is_green = count >= CHALLENGE_MIN_MEMBERS
    leader_checked = clan.get("leader_id") in checked
    return {
        "clan_id": clan["id"],
        "required": CHALLENGE_MIN_MEMBERS,
        "count": count,
        "is_green": is_green,
        "leader_checked_in": leader_checked,
        "ready_for_challenge": bool(is_green and leader_checked),
        "checked_in_ids": checked,
        "updated_at": doc.get("updated_at"),
    }


async def _sync_live_match_attendance(clan_id: str, user_id: str, checked_in: bool) -> None:
    live_matches = await db.matches.find(
        {
            "status": "live",
            "$or": [{"clan_a_id": clan_id}, {"clan_b_id": clan_id}],
        },
        {"_id": 0, "id": 1, "clan_a_id": 1, "attendance_a_ids": 1, "attendance_b_ids": 1},
    ).to_list(200)
    for m in live_matches:
        side_key = "attendance_a_ids" if m.get("clan_a_id") == clan_id else "attendance_b_ids"
        current_ids = list(m.get(side_key, []))
        if checked_in:
            if user_id in current_ids:
                continue
            await db.matches.update_one({"id": m["id"]}, {"$addToSet": {side_key: user_id}})
            await db.users.update_one({"id": user_id}, {"$inc": {"attendances": 1}})
        else:
            if user_id not in current_ids:
                continue
            await db.matches.update_one({"id": m["id"]}, {"$pull": {side_key: user_id}})


async def _initial_match_attendance_ids(clan: dict) -> list:
    summary = await _clan_attendance_summary(clan)
    return list(summary.get("checked_in_ids", []))


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
        "isPlusClan": False,
        "created_at": iso(now_utc()),
    }
    await db.clans.insert_one(clan)
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"clan_id": clan["id"], "clan_joined_at": iso(now_utc())}},
    )
    await _create_news_post(
        kind="system_profile",
        title=f"تم إنشاء فريق جديد باسم {clan['name']}",
        body=f"تم إنشاء كلان [{clan['tag']}] بنجاح.",
        payload={"clan_id": clan["id"], "clan_name": clan["name"], "clan_tag": clan["tag"]},
        created_by=user["id"],
        created_by_role=user.get("role", "player"),
    )
    await _discord_enqueue_clan_role_create(clan)
    await _discord_enqueue_clan_role_sync_member(user_id=user["id"], old_clan_id="", new_clan_id=clan["id"])
    clan.pop("_id", None)
    return clan


@api.get("/clans")
async def list_clans(q: str = ""):
    query = {"archived": {"$ne": True}}
    if q:
        query = {"$and": [
            query,
            {"$or": [
                {"id": {"$regex": q, "$options": "i"}},
                {"name": {"$regex": q, "$options": "i"}},
                {"tag": {"$regex": q, "$options": "i"}},
            ]},
        ]}
    clans = await db.clans.find(query, {"_id": 0}).sort("points", -1).to_list(100)
    for c in clans:
        c["isPlusClan"] = bool(c.get("isPlusClan") or _clan_is_plus(c))
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
    clan["isPlusClan"] = bool(clan.get("isPlusClan") or _clan_is_plus(clan) or max_members == CLAN_LIMIT_PLUS)
    clan["attendance"] = await _clan_attendance_summary(clan)
    clan["suspension_remaining_seconds"] = _clan_suspension_remaining_seconds(clan)
    clan["suspension_active"] = clan["suspension_remaining_seconds"] > 0
    return clan


@api.put("/clans/{clan_id}/logo")
async def update_clan_logo(clan_id: str, body: ClanLogoUpdateIn, request: Request, user: dict = Depends(get_current_user)):
    _rate_limit_or_429(request, "upload:clan_logo", limit=20, window_seconds=10 * 60)
    clan = await _get_clan(clan_id)
    if not _is_clan_staff(clan, user):
        raise HTTPException(403, "فقط القائد أو النواب")
    logo = (body.logo or "").strip()
    if not logo:
        raise HTTPException(400, "يجب إدخال شعار صالح")
    await db.clans.update_one({"id": clan_id}, {"$set": {"logo": logo, "logo_updated_at": iso(now_utc())}})
    await _create_news_post(
        kind="system_profile",
        title=f"تم تجديد شعار كلان {clan.get('name', '')}",
        body="تم تحديث الشعار بنجاح.",
        payload={"clan_id": clan_id, "logo": logo},
        created_by=user["id"],
        created_by_role=user.get("role", "player"),
    )
    fresh = await db.clans.find_one({"id": clan_id}, {"_id": 0})
    return fresh


@api.post("/clans/{clan_id}/logo/upload")
@api.put("/clans/{clan_id}/logo/upload")
@api.post("/clans/{clan_id}/upload-logo")
@api.put("/clans/{clan_id}/upload-logo")
async def upload_clan_logo(
    clan_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    _rate_limit_or_429(request, "upload:clan_logo_file", limit=20, window_seconds=10 * 60)
    clan = await _get_clan(clan_id)
    if not _is_clan_staff(clan, user):
        raise HTTPException(403, "فقط القائد أو النواب")

    allowed_mimes = {"image/gif", "image/png", "image/jpeg", "image/jpg"}
    incoming_mime = (file.content_type or "").lower()
    if incoming_mime not in allowed_mimes:
        raise HTTPException(400, "صيغة الشعار غير مدعومة. المسموح: GIF, PNG, JPG")

    filename = (file.filename or "").lower()
    requested_gif = incoming_mime == "image/gif" or filename.endswith(".gif")
    is_plus_clan = _clan_is_plus(clan)
    if requested_gif and not is_plus_clan:
        raise HTTPException(403, "عذراً، ميزة الشعار المتحرك GIF حصرية لكلانات البلس!")

    max_bytes = CLAN_LOGO_GIF_MAX_BYTES if requested_gif else CLAN_LOGO_MAX_BYTES
    CHUNK = 1024 * 256
    buf = bytearray()
    written = 0
    try:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                limit_mb = max_bytes // (1024 * 1024)
                raise HTTPException(400, f"حجم الشعار كبير. الحد الأقصى {limit_mb}MB")
            buf.extend(chunk)
    finally:
        await file.close()

    if not buf:
        raise HTTPException(400, "الملف فارغ")

    try:
        img = PILImage.open(io.BytesIO(bytes(buf)))
        img_fmt = (img.format or "").upper()
        img.verify()
    except Exception:
        raise HTTPException(400, "الصورة تالفة أو غير صالحة")

    if img_fmt not in {"JPEG", "PNG", "GIF"}:
        raise HTTPException(400, f"صيغة الشعار غير مدعومة ({img_fmt}). المسموح: GIF, PNG, JPG")

    if img_fmt == "GIF" and not is_plus_clan:
        raise HTTPException(403, "عذراً، ميزة الشعار المتحرك GIF حصرية لكلانات البلس!")

    ext = "jpg" if img_fmt == "JPEG" else img_fmt.lower()
    fname = f"{uuid.uuid4()}.{ext}"
    dest = CLAN_LOGO_UPLOAD_DIR / fname
    with dest.open("wb") as out:
        out.write(bytes(buf))

    logo_url = f"/api/uploads/clan_logos/{fname}"
    await db.clans.update_one(
        {"id": clan_id},
        {"$set": {"logo": logo_url, "logo_updated_at": iso(now_utc())}},
    )

    return {"ok": True, "url": logo_url, "size": written, "mime": incoming_mime}


@api.post("/clans/upload-logo")
@api.put("/clans/upload-logo")
async def upload_clan_logo_legacy(
    request: Request,
    clan_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Compatibility route for older frontend integrations."""
    return await upload_clan_logo(clan_id=clan_id, request=request, file=file, user=user)


@api.get("/clans/{clan_id}/attendance")
async def get_clan_attendance(clan_id: str):
    clan = await _get_clan(clan_id)
    summary = await _clan_attendance_summary(clan)
    checked_in_users = await db.users.find(
        {"id": {"$in": summary["checked_in_ids"]}},
        {"_id": 0, "id": 1, "username": 1, "act": 1, "avatar": 1},
    ).to_list(200)
    return {
        "summary": {
            "count": summary["count"],
            "required": summary["required"],
            "is_green": summary["is_green"],
            "leader_checked_in": summary["leader_checked_in"],
            "ready_for_challenge": summary["ready_for_challenge"],
            "updated_at": summary["updated_at"],
        },
        "checked_in": checked_in_users,
    }


@api.post("/clans/{clan_id}/attendance/checkin")
async def attendance_checkin(clan_id: str, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if user.get("clan_id") != clan_id or user["id"] not in clan.get("member_ids", []):
        raise HTTPException(403, "فقط أعضاء الكلان يمكنهم التحضير")
    now_iso = iso(now_utc())
    await db.clan_attendance.update_one(
        {"clan_id": clan_id},
        {
            "$addToSet": {"checked_in_ids": user["id"]},
            "$push": {"attendance_events": {"user_id": user["id"], "action": "checkin", "at": now_iso}},
            "$set": {
                "updated_at": now_iso,
                f"last_interaction_at.{user['id']}": now_iso,
            },
        },
        upsert=True,
    )
    await _sync_live_match_attendance(clan_id, user["id"], checked_in=True)
    return await get_clan_attendance(clan_id)


@api.post("/clans/{clan_id}/attendance/checkout")
async def attendance_checkout(clan_id: str, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if user.get("clan_id") != clan_id or user["id"] not in clan.get("member_ids", []):
        raise HTTPException(403, "فقط أعضاء الكلان يمكنهم تعديل التحضير")
    now_iso = iso(now_utc())
    await db.clan_attendance.update_one(
        {"clan_id": clan_id},
        {
            "$pull": {"checked_in_ids": user["id"]},
            "$set": {
                "updated_at": now_iso,
                f"last_interaction_at.{user['id']}": now_iso,
            },
        },
        upsert=True,
    )
    await _sync_live_match_attendance(clan_id, user["id"], checked_in=False)
    return await get_clan_attendance(clan_id)


@api.get("/clans/{clan_id}/mvp-leaderboard")
async def clan_mvp_leaderboard(clan_id: str):
    clan = await _get_clan(clan_id)
    docs = await db.users.find(
        {"id": {"$in": clan.get("member_ids", [])}},
        {"_id": 0, "id": 1, "username": 1, "act": 1, "mvp_count": 1, "wins": 1, "losses": 1, "attendances": 1},
    ).to_list(200)
    docs.sort(key=lambda u: (u.get("mvp_count", 0), u.get("wins", 0), -u.get("losses", 0)), reverse=True)
    return [
        {
            "id": u["id"],
            "username": u.get("username"),
            "act": u.get("act"),
            "mvp_count": u.get("mvp_count", 0),
            "wins": u.get("wins", 0),
            "losses": u.get("losses", 0),
            "attendances": u.get("attendances", 0),
        }
        for u in docs[:10]
    ]


@api.delete("/clans/{clan_id}")
async def delete_clan(clan_id: str, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if user["id"] != clan["leader_id"] and not is_staff(user):
        raise HTTPException(403, "ليس لديك صلاحية")
    member_ids = list(clan.get("member_ids", []))
    await db.users.update_many({"clan_id": clan_id}, {"$set": {"clan_id": None}})
    await db.clans.delete_one({"id": clan_id})
    for member_id in member_ids:
        await _discord_enqueue_clan_role_sync_member(user_id=member_id, old_clan_id=clan_id, new_clan_id="")
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
            old_clan_id = (target.get("clan_id") or "").strip()
            _assert_no_cooldown(target)
            _assert_act_set(target)
            await db.users.update_one(
                {"id": req["user_id"]},
                {"$set": {"clan_id": clan_id, "clan_cooldown_until": None, "clan_joined_at": iso(now_utc())}},
            )
            await db.clans.update_one({"id": clan_id}, {"$addToSet": {"member_ids": req["user_id"]}})
            await _discord_enqueue_clan_role_sync_member(
                user_id=req["user_id"],
                old_clan_id=old_clan_id,
                new_clan_id=clan_id,
            )
            granted = await _maybe_grant_full_clan_reward(clan_id)
            if target.get("last_clan_id") and target.get("last_clan_id") != clan_id:
                await _record_transfer_market_event(
                    user_doc=target,
                    old_clan_id=target.get("last_clan_id"),
                    new_clan_id=clan_id,
                    old_joined_at=target.get("last_clan_joined_at"),
                    old_left_at=target.get("last_clan_left_at"),
                )
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
    invite_msg = f"📩 عرض تعاقد رسمي! يرغب كلان {clan['name']} بانضمامك لصفوفه كلاعب محترف."
    await _create_notification(
        user_id=body.user_id,
        sender_id=clan_id,
        n_type=NOTIFICATION_TYPE_CLAN_INVITE,
        status="pending",
        kind="clan_invite",
        title="دعوة كلان",
        body=invite_msg,
        message=invite_msg,
        data={
            "join_request_id": inv["id"],
            "clan_id": clan_id,
            "clan_name": clan.get("name", ""),
            "route": f"/clans/{clan_id}",
        },
    )
    inv.pop("_id", None)
    return inv


@api.post("/clans/{clan_id}/contract-offer")
async def offer_contract_to_free_agent(clan_id: str, body: ContractOfferIn, user: dict = Depends(get_current_user)):
    clan = await _get_clan(clan_id)
    if not _is_clan_staff(clan, user):
        raise HTTPException(403, "فقط قادة الكلان أو النواب")
    if user.get("clan_id") != clan_id and not is_staff(user):
        raise HTTPException(403, "هذا ليس كلانك")

    target = await db.users.find_one({"id": body.user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "اللاعب غير موجود")
    if target.get("clan_id"):
        raise HTTPException(400, "العرض مخصص للاعبين الأحرار فقط")

    max_members, _ = await _leader_limits(clan)
    if len(clan.get("member_ids", [])) >= max_members:
        raise HTTPException(400, "الكلان ممتلئ")

    existing = await db.join_requests.find_one(
        {
            "clan_id": clan_id,
            "user_id": body.user_id,
            "type": "contract_offer",
            "status": "pending",
        },
        {"_id": 0, "id": 1},
    )
    if existing:
        raise HTTPException(400, "يوجد عرض تعاقد معلّق لهذا اللاعب بالفعل")

    terms = (body.terms or "").strip()
    invite_doc = {
        "id": str(uuid.uuid4()),
        "clan_id": clan_id,
        "user_id": body.user_id,
        "username": target.get("username") or "",
        "status": "pending",
        "type": "contract_offer",
        "terms": terms,
        "created_by": user.get("id"),
        "created_at": iso(now_utc()),
    }
    await db.join_requests.insert_one(invite_doc)

    msg = f"📩 عرض تعاقد رسمي! يرغب كلان {clan['name']} بانضمامك لصفوفه كلاعب محترف."
    if terms:
        msg = f"{msg}\n\nالشروط: {terms}"

    notif = await _create_notification(
        user_id=body.user_id,
        sender_id=clan_id,
        n_type=NOTIFICATION_TYPE_CLAN_INVITE,
        status="pending",
        kind="contract_offer",
        title="عرض تعاقد رسمي",
        body=msg,
        message=msg,
        data={
            "join_request_id": invite_doc["id"],
            "clan_id": clan_id,
            "clan_name": clan.get("name", ""),
            "route": f"/players/{body.user_id}",
            "terms": terms,
        },
    )

    return {
        "ok": True,
        "offer_id": invite_doc["id"],
        "notification_id": notif.get("id"),
        "status": "pending",
    }


@api.get("/me/invites")
async def my_invites(user: dict = Depends(get_current_user)):
    invs = await db.join_requests.find(
        {"user_id": user["id"], "type": {"$in": ["invite", "contract_offer"]}, "status": "pending"}, {"_id": 0}
    ).to_list(100)
    for inv in invs:
        clan = await db.clans.find_one({"id": inv["clan_id"]}, {"_id": 0})
        if clan:
            inv["clan_name"] = clan["name"]
            inv["clan_tag"] = clan["tag"]
    return invs


@api.post("/invites/{inv_id}")
async def respond_invite(inv_id: str, body: HandleRequestIn, user: dict = Depends(get_current_user)):
    inv = await db.join_requests.find_one(
        {"id": inv_id, "user_id": user["id"], "type": {"$in": ["invite", "contract_offer"]}},
        {"_id": 0},
    )
    if not inv:
        raise HTTPException(404, "الدعوة غير موجودة")
    now_iso = iso(now_utc())
    if body.action == "accept" and not user.get("clan_id"):
        old_clan_id = (user.get("clan_id") or "").strip()
        _assert_no_cooldown(user)
        _assert_act_set(user)
        clan = await _get_clan(inv["clan_id"])
        max_members, _ = await _leader_limits(clan)
        if len(clan.get("member_ids", [])) >= max_members:
            raise HTTPException(400, "الكلان ممتلئ")
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"clan_id": inv["clan_id"], "clan_cooldown_until": None, "clan_joined_at": iso(now_utc())}},
        )
        await db.clans.update_one({"id": inv["clan_id"]}, {"$addToSet": {"member_ids": user["id"]}})
        await _discord_enqueue_clan_role_sync_member(
            user_id=user["id"],
            old_clan_id=old_clan_id,
            new_clan_id=inv["clan_id"],
        )
        granted = await _maybe_grant_full_clan_reward(inv["clan_id"])
        if user.get("last_clan_id") and user.get("last_clan_id") != inv["clan_id"]:
            await _record_transfer_market_event(
                user_doc=user,
                old_clan_id=user.get("last_clan_id"),
                new_clan_id=inv["clan_id"],
                old_joined_at=user.get("last_clan_joined_at"),
                old_left_at=user.get("last_clan_left_at"),
            )
    await db.join_requests.update_one({"id": inv_id}, {"$set": {"status": body.action, "updated_at": now_iso}})
    await db.notifications.update_many(
        {
            "user_id": user["id"],
            "type": NOTIFICATION_TYPE_CLAN_INVITE,
            "status": "pending",
            "data.join_request_id": inv_id,
        },
        {"$set": {"status": "accepted" if body.action == "accept" else "rejected", "read_at": now_iso, "updated_at": now_iso}},
    )
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
    await _discord_enqueue_clan_role_sync_member(user_id=member_id, old_clan_id=clan_id, new_clan_id="")
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
    await _discord_enqueue_clan_role_sync_member(user_id=user["id"], old_clan_id=clan_id, new_clan_id="")
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
        "league_id": body.league_id,
        "status": "pending",
        "created_by": user["id"],
        "created_at": iso(now_utc()),
        "match_id": None,
    }
    await db.challenges.insert_one(ch)

    opponent_staff_ids = list(dict.fromkeys([
        opponent.get("leader_id"),
        *(opponent.get("vice_leader_ids") or []),
    ]))
    challenge_msg = f"⚔️ تحدي جديد! كلان {challenger['name']} يرسل طلباً لتحدي كلانك في مواجهة حاسمة."
    for uid in [x for x in opponent_staff_ids if x]:
        await _create_notification(
            user_id=uid,
            sender_id=clan_id,
            n_type=NOTIFICATION_TYPE_CLAN_CHALLENGE,
            status="pending",
            kind="clan_challenge",
            title="تحدي جديد",
            body=challenge_msg,
            message=challenge_msg,
            data={
                "challenge_id": ch["id"],
                "challenger_clan_id": clan_id,
                "challenger_clan_name": challenger.get("name", ""),
                "route": f"/clans/{opponent['id']}",
            },
        )

    ch.pop("_id", None)
    return ch


@api.post("/clans/{target_clan_id}/instant-challenge")
async def instant_challenge(target_clan_id: str, user: dict = Depends(get_current_user)):
    challenger_clan_id = user.get("clan_id")
    if not challenger_clan_id:
        raise HTTPException(400, "يجب أن تكون داخل كلان")
    challenger = await _get_clan(challenger_clan_id)
    target = await _get_clan(target_clan_id)
    if challenger["id"] == target["id"]:
        raise HTTPException(400, "لا يمكن تحدي نفس الكلان")
    if user["id"] != challenger.get("leader_id") and not is_staff(user):
        raise HTTPException(403, "التحدي المباشر متاح لقائد الكلان فقط")
    _assert_clan_can_match(challenger)
    _assert_clan_can_match(target)
    target_attendance = await _clan_attendance_summary(target)
    if not target_attendance["is_green"]:
        raise HTTPException(400, "الكلان الخصم غير جاهز حالياً (التحضير أقل من 6)")
    own_attendance = await _clan_attendance_summary(challenger)
    if not own_attendance["ready_for_challenge"]:
        raise HTTPException(400, "يجب أن يصل التحضير إلى 6 لاعبين على الأقل مع حضور القائد")
    await _check_match_pair_cooldown(challenger["id"], target["id"])
    existing = await db.challenges.find_one({
        "status": "pending",
        "$or": [
            {"challenger_clan_id": challenger["id"], "opponent_clan_id": target["id"]},
            {"challenger_clan_id": target["id"], "opponent_clan_id": challenger["id"]},
        ],
    })
    if existing:
        raise HTTPException(400, "هناك طلب تحدٍ معلّق بالفعل بين الكلانين")
    ch = {
        "id": str(uuid.uuid4()),
        "challenger_clan_id": challenger["id"],
        "challenger_name": challenger["name"],
        "challenger_tag": challenger["tag"],
        "opponent_clan_id": target["id"],
        "opponent_name": target["name"],
        "opponent_tag": target["tag"],
        "notes": "التحدي المباشر • رايفلز شيلد",
        "league_id": None,
        "status": "pending",
        "created_by": user["id"],
        "created_at": iso(now_utc()),
        "match_id": None,
        "is_instant": True,
    }
    await db.challenges.insert_one(ch)

    target_staff_ids = list(dict.fromkeys([
        target.get("leader_id"),
        *(target.get("vice_leader_ids") or []),
    ]))
    challenge_msg = f"⚔️ تحدي جديد! كلان {challenger['name']} يرسل طلباً لتحدي كلانك في مواجهة حاسمة."
    for uid in [x for x in target_staff_ids if x]:
        await _create_notification(
            user_id=uid,
            sender_id=challenger["id"],
            n_type=NOTIFICATION_TYPE_CLAN_CHALLENGE,
            status="pending",
            kind="clan_challenge",
            title="تحدي جديد",
            body=challenge_msg,
            message=challenge_msg,
            data={
                "challenge_id": ch["id"],
                "challenger_clan_id": challenger["id"],
                "challenger_clan_name": challenger.get("name", ""),
                "route": f"/clans/{target['id']}",
            },
        )

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
    now_iso = iso(now_utc())
    if body.action == "reject":
        await db.challenges.update_one({"id": ch_id}, {"$set": {"status": "rejected"}})
        await db.notifications.update_many(
            {
                "user_id": user["id"],
                "type": NOTIFICATION_TYPE_CLAN_CHALLENGE,
                "status": "pending",
                "data.challenge_id": ch_id,
            },
            {"$set": {"status": "rejected", "read_at": now_iso, "updated_at": now_iso}},
        )
        challenger = await _get_clan(ch["challenger_clan_id"])
        challenger_staff = list(dict.fromkeys([challenger.get("leader_id"), *(challenger.get("vice_leader_ids") or [])]))
        rejected_msg = f"تم رفض التحدي من كلان {opponent['name']}."
        for uid in [x for x in challenger_staff if x]:
            await _create_notification(
                user_id=uid,
                sender_id=opponent.get("id", ""),
                n_type=NOTIFICATION_TYPE_GENERAL,
                status="pending",
                kind="clan_challenge_result",
                title="تم رفض التحدي",
                body=rejected_msg,
                message=rejected_msg,
                data={"challenge_id": ch_id, "route": f"/clans/{challenger['id']}"},
            )
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
    attendance_a_ids = await _initial_match_attendance_ids(challenger)
    attendance_b_ids = await _initial_match_attendance_ids(opponent)
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
        "attendance_a_ids": attendance_a_ids,
        "attendance_b_ids": attendance_b_ids,
        "mvp_votes": [],
        "mvp_eligible_ids": [],
        "mvp_winner_user_id": None,
        "mvp_finalized_at": None,
        "notes": ch.get("notes", ""),
        "league_id": ch.get("league_id"),
        "created_at": iso(now_utc()),
        "finished_at": None,
    }
    await db.matches.insert_one(m)
    await _post_sanad_welcome(m["id"])
    all_attendees = list({*attendance_a_ids, *attendance_b_ids})
    if all_attendees:
        await db.users.update_many({"id": {"$in": all_attendees}}, {"$inc": {"attendances": 1}})
    await _create_news_post(
        kind="match-start",
        title=f"انطلاق مباراة جديدة • {ch['challenger_name']} ضد {ch['opponent_name']}",
        body="تم قبول التحدي وبدأت المباراة الآن",
    )
    await db.challenges.update_one(
        {"id": ch_id}, {"$set": {"status": "accepted", "match_id": m["id"]}}
    )
    await db.notifications.update_many(
        {
            "user_id": user["id"],
            "type": NOTIFICATION_TYPE_CLAN_CHALLENGE,
            "status": "pending",
            "data.challenge_id": ch_id,
        },
        {"$set": {"status": "accepted", "read_at": now_iso, "updated_at": now_iso}},
    )

    challenger_staff = list(dict.fromkeys([challenger.get("leader_id"), *(challenger.get("vice_leader_ids") or [])]))
    accepted_msg = f"تم قبول التحدي من كلان {opponent['name']}، وتم إنشاء لوبي المباراة."
    for uid in [x for x in challenger_staff if x]:
        await _create_notification(
            user_id=uid,
            sender_id=opponent.get("id", ""),
            n_type=NOTIFICATION_TYPE_GENERAL,
            status="pending",
            kind="clan_challenge_result",
            title="تم قبول التحدي",
            body=accepted_msg,
            message=accepted_msg,
            data={"challenge_id": ch_id, "match_id": m["id"], "route": f"/matches/{m['id']}"},
        )

    m.pop("_id", None)
    asyncio.create_task(_send_discord_embed(
        title=f"🔴 Match Started: {ch['challenger_name']} [{ch['challenger_tag']}] vs {ch['opponent_name']} [{ch['opponent_tag']}]",
        description="تم قبول التحدي — البطولة تشتعل!",
        color=0xFF3344,
    ))
    asyncio.create_task(_ai_welcome_for_match(
        m["id"],
        {"name": ch["challenger_name"], "tag": ch["challenger_tag"]},
        {"name": ch["opponent_name"], "tag": ch["opponent_tag"]},
        league_id=ch.get("league_id"),
    ))
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
    m["attendance_a_count"] = len(m.get("attendance_a_ids", []) or [])
    m["attendance_b_count"] = len(m.get("attendance_b_ids", []) or [])
    return m


def _count_maps(maps: list) -> tuple[int, int]:
    return (
        sum(1 for mp in maps if mp.get("winner") and mp["winner"] == "A"),
        sum(1 for mp in maps if mp.get("winner") and mp["winner"] == "B"),
    )


async def _post_match_score_news(match: dict, won_a: int, won_b: int) -> None:
    clan_a = await db.clans.find_one({"id": match["clan_a_id"]}, {"_id": 0, "name": 1})
    clan_b = await db.clans.find_one({"id": match["clan_b_id"]}, {"_id": 0, "name": 1})
    if not clan_a or not clan_b:
        return
    title = f"تحديث النتيجة • {clan_a['name']} {won_a} - {won_b} {clan_b['name']}"
    body = f"المباراة: {match.get('id', '')}"
    await _create_news_post(kind="match-score", title=title, body=body)


POINTS_WIN = 3
POINTS_LOSS = -1
POINTS_WITHDRAW = -3

GRACE_PERIOD_SECONDS = 10 * 60  # 10-minute grace period to claim a map win
PRAYER_BREAK_SECONDS = 10 * 60  # 10-minute prayer break that pauses the grace timer
MATCH_PAIR_COOLDOWN_HOURS = 3   # Same two clans cannot match within 3 hours


async def _apply_league_standings(league_id: Optional[str], clan_id: str,
                                  points_delta: int, win: bool = False, loss: bool = False) -> None:
    """Upsert per-league standings for a clan. Independent of global clan.points."""
    if not league_id:
        return
    inc = {"points": points_delta}
    if win:
        inc["wins"] = 1
    if loss:
        inc["losses"] = 1
    await db.league_standings.update_one(
        {"league_id": league_id, "clan_id": clan_id},
        {"$inc": inc, "$set": {"updated_at": iso(now_utc())}},
        upsert=True,
    )


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
FREE_VIDEO_MAX_BYTES = 80 * 1024 * 1024      # 80 MB
UPLOAD_DIR = ROOT_DIR / "uploads" / "videos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CLAN_LOGO_UPLOAD_DIR = ROOT_DIR / "uploads" / "clan_logos"
CLAN_LOGO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
GUARD_UPLOAD_DIR = ROOT_DIR / "uploads" / "guard"
GUARD_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR = ROOT_DIR / "static" / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
CLAN_LOGO_MAX_BYTES = 2 * 1024 * 1024       # 2 MB for PNG/JPG
CLAN_LOGO_GIF_MAX_BYTES = 6 * 1024 * 1024   # 6 MB for Plus GIF logos


def _unique_ids(items: list) -> list:
    return list(dict.fromkeys([x for x in (items or []) if x]))


def _normalize_gaming_platform(value: Optional[str]) -> str:
    v = (value or "pc").strip().lower()
    if v in {"ps", "playstation", "ps5"}:
        return "ps5"
    if v in {"xbox", "seriesx", "series"}:
        return "xbox"
    if v in {"console", "ps5", "xbox"}:
        return v
    return "pc"


def _guard_session_is_active(session_doc: Optional[dict]) -> bool:
    if not session_doc:
        return False
    if (session_doc.get("status") or "").lower() != "active":
        return False
    last_seen_raw = session_doc.get("last_seen_at")
    if not last_seen_raw:
        return False
    try:
        last_seen_dt = datetime.fromisoformat(last_seen_raw)
    except Exception:
        return False
    return (now_utc() - last_seen_dt).total_seconds() <= GUARD_HEARTBEAT_STALE_SECONDS


def _guard_status_badge(platform: str, is_active: bool) -> str:
    if platform in {"ps5", "xbox", "console"}:
        return "console_validated"
    if is_active:
        return "guard_active"
    return "guard_inactive"


class _GuardPresenceHub:
    def __init__(self) -> None:
        self._sockets_by_match: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, match_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._sockets_by_match[match_id].add(websocket)

    async def disconnect(self, match_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._sockets_by_match.get(match_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._sockets_by_match.pop(match_id, None)

    async def broadcast(self, match_id: str, payload: dict) -> None:
        async with self._lock:
            sockets = list(self._sockets_by_match.get(match_id, set()))
        if not sockets:
            return
        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                current = self._sockets_by_match.get(match_id, set())
                for ws in dead:
                    current.discard(ws)
                if not current:
                    self._sockets_by_match.pop(match_id, None)


_guard_presence_hub = _GuardPresenceHub()


async def _resolve_guard_roster(match: dict) -> dict:
    if not match:
        return {"players": [], "all_pc_ready": True, "pc_required_count": 0, "pc_ready_count": 0}

    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    side_a_staff = _unique_ids([a.get("leader_id")] + (a.get("vice_leader_ids") or []))
    side_b_staff = _unique_ids([b.get("leader_id")] + (b.get("vice_leader_ids") or []))

    attendance = _unique_ids((match.get("attendance_a_ids") or []) + (match.get("attendance_b_ids") or []))
    participant_ids = _unique_ids(attendance + side_a_staff + side_b_staff)
    if not participant_ids:
        return {"players": [], "all_pc_ready": True, "pc_required_count": 0, "pc_ready_count": 0}

    users = await db.users.find(
        {"id": {"$in": participant_ids}},
        {"_id": 0, "id": 1, "username": 1, "clan_id": 1, "gaming_platform": 1, "act": 1},
    ).to_list(200)
    user_map = {u["id"]: u for u in users if u.get("id")}

    sessions = await db.guard_sessions.find(
        {"match_id": match["id"], "user_id": {"$in": participant_ids}},
        {"_id": 0},
    ).to_list(400)
    latest_session_by_user: dict[str, dict] = {}
    for sess in sessions:
        uid = sess.get("user_id")
        if not uid:
            continue
        prev = latest_session_by_user.get(uid)
        if not prev:
            latest_session_by_user[uid] = sess
            continue
        prev_ts = prev.get("last_seen_at") or ""
        cur_ts = sess.get("last_seen_at") or ""
        if cur_ts >= prev_ts:
            latest_session_by_user[uid] = sess

    players = []
    pc_required_count = 0
    pc_ready_count = 0
    for uid in participant_ids:
        u = user_map.get(uid)
        if not u:
            continue
        clan_id = u.get("clan_id")
        side = "A" if clan_id == match.get("clan_a_id") else "B" if clan_id == match.get("clan_b_id") else None
        platform = _normalize_gaming_platform(u.get("gaming_platform") or "pc")
        sess = latest_session_by_user.get(uid)
        active = _guard_session_is_active(sess)

        if platform == "pc":
            pc_required_count += 1
            if active:
                pc_ready_count += 1

        players.append({
            "user_id": uid,
            "username": u.get("username") or uid,
            "side": side,
            "platform": platform,
            "status": _guard_status_badge(platform, active),
            "guard_active": active,
            "last_seen_at": sess.get("last_seen_at") if sess else None,
        })

    return {
        "players": players,
        "all_pc_ready": pc_ready_count >= pc_required_count,
        "pc_required_count": pc_required_count,
        "pc_ready_count": pc_ready_count,
    }


async def _broadcast_guard_status(match_id: str) -> None:
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        return
    snapshot = await _resolve_guard_roster(match)
    await _guard_presence_hub.broadcast(match_id, {
        "event": "guard_status",
        "match_id": match_id,
        **snapshot,
    })


def _eligible_attendance_ids(match: dict, side: str) -> list:
    key = "attendance_a_ids" if side == "A" else "attendance_b_ids"
    return _unique_ids(match.get(key, []))


async def _ensure_mvp_voting_initialized(match: dict) -> dict:
    if match.get("mvp_eligible_ids"):
        return match
    eligible = _unique_ids((match.get("attendance_a_ids") or []) + (match.get("attendance_b_ids") or []))
    await db.matches.update_one(
        {"id": match["id"]},
        {"$set": {"mvp_eligible_ids": eligible}},
    )
    match["mvp_eligible_ids"] = eligible
    if "mvp_votes" not in match:
        match["mvp_votes"] = []
    return match


async def _finalize_mvp_if_ready(match: dict) -> Optional[str]:
    if match.get("mvp_winner_user_id"):
        return match.get("mvp_winner_user_id")
    eligible = _unique_ids(match.get("mvp_eligible_ids", []))
    votes = match.get("mvp_votes", []) or []
    if not votes:
        return None
    voter_ids = _unique_ids([v.get("voter_id") for v in votes if v.get("voter_id")])
    if eligible and len(voter_ids) < len(eligible):
        return None
    counts = {}
    first_seen = {}
    for idx, v in enumerate(votes):
        candidate = v.get("candidate_id")
        if not candidate:
            continue
        counts[candidate] = counts.get(candidate, 0) + 1
        if candidate not in first_seen:
            first_seen[candidate] = idx
    if not counts:
        return None
    winner_id = sorted(counts.keys(), key=lambda cid: (-counts[cid], first_seen.get(cid, 10**9), cid))[0]
    await db.matches.update_one(
        {"id": match["id"], "mvp_winner_user_id": {"$in": [None, ""]}},
        {"$set": {"mvp_winner_user_id": winner_id, "mvp_finalized_at": iso(now_utc())}},
    )
    fresh = await db.matches.find_one({"id": match["id"]}, {"_id": 0, "mvp_winner_user_id": 1})
    if (fresh or {}).get("mvp_winner_user_id") == winner_id:
        await db.users.update_one({"id": winner_id}, {"$inc": {"mvp_count": 1}})
        return winner_id
    return (fresh or {}).get("mvp_winner_user_id")

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
    # Per-league standings (decoupled)
    league_id = match.get("league_id")
    if league_id:
        await _apply_league_standings(league_id, winner, POINTS_WIN, win=True)
        await _apply_league_standings(league_id, loser, POINTS_LOSS, loss=True)
    # Career stats: Rivals Shield rule (ALL checked-in attendees get result)
    winner_side = "A" if winner == match["clan_a_id"] else "B"
    loser_side = "B" if winner_side == "A" else "A"
    winner_attendees = _eligible_attendance_ids(match, winner_side)
    loser_attendees = _eligible_attendance_ids(match, loser_side)
    if winner_attendees:
        await db.users.update_many({"id": {"$in": winner_attendees}}, {"$inc": {"wins": 1}})
    if loser_attendees:
        await db.users.update_many({"id": {"$in": loser_attendees}}, {"$inc": {"losses": 1}})
    await _ensure_mvp_voting_initialized(match)
    winner_clan = await db.clans.find_one({"id": winner}, {"_id": 0, "name": 1})
    loser_clan = await db.clans.find_one({"id": loser}, {"_id": 0, "name": 1})
    if winner_clan and loser_clan:
        await _create_news_post(
            kind="match-final",
            title=f"نهاية المباراة • فوز {winner_clan['name']}",
            body=f"النتيجة النهائية: {winner_clan['name']} {max(won_a, won_b)} - {min(won_a, won_b)} {loser_clan['name']}",
        )
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
    attendance_a_ids = await _initial_match_attendance_ids(a)
    attendance_b_ids = await _initial_match_attendance_ids(b)
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
        "attendance_a_ids": attendance_a_ids,
        "attendance_b_ids": attendance_b_ids,
        "mvp_votes": [],
        "mvp_eligible_ids": [],
        "mvp_winner_user_id": None,
        "mvp_finalized_at": None,
        "notes": body.notes or "",
        "league_id": body.league_id,
        "created_at": iso(now_utc()),
        "finished_at": None,
    }
    await db.matches.insert_one(m)
    await _post_sanad_welcome(m["id"])
    all_attendees = list({*attendance_a_ids, *attendance_b_ids})
    if all_attendees:
        await db.users.update_many({"id": {"$in": all_attendees}}, {"$inc": {"attendances": 1}})
    await _create_news_post(
        kind="match-start",
        title=f"انطلاق مباراة جديدة • {a['name']} ضد {b['name']}",
        body="بدأت مباراة جديدة في رايفلز شيلد",
    )
    m.pop("_id", None)
    asyncio.create_task(_send_discord_embed(
        title=f"🔴 Match Started: {a['name']} [{a['tag']}] vs {b['name']} [{b['tag']}]",
        description="BO3 • Call of Duty — المباراة بدأت، تابع الشات الحي للحصول على آخر التحديثات!",
        color=0xFF3344,
    ))
    asyncio.create_task(_ai_welcome_for_match(m["id"], a, b, league_id=body.league_id))
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


@api.get("/matches/{match_id}/guard/status")
async def get_match_guard_status(match_id: str, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    is_participant = user.get("clan_id") in (match.get("clan_a_id"), match.get("clan_b_id"))
    if (not is_participant) and (not is_staff(user)):
        raise HTTPException(403, "هذه الحالة متاحة لأطراف المباراة والإدارة")
    snapshot = await _resolve_guard_roster(match)
    return {
        "match_id": match_id,
        **snapshot,
        "updated_at": iso(now_utc()),
    }


@api.get("/guard/launcher-link/{match_id}")
async def guard_launcher_link(match_id: str, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    is_participant = user.get("clan_id") in (match.get("clan_a_id"), match.get("clan_b_id"))
    if (not is_participant) and (not is_staff(user)):
        raise HTTPException(403, "للأطراف المشاركة فقط")

    token = (user.get("guard_session_token") or "").strip()
    if not token:
        token = secrets.token_urlsafe(24)
        await db.users.update_one({"id": user["id"]}, {"$set": {"guard_session_token": token}})

    deep_link = f"rivalsguard://connect?{urlencode({'match_id': match_id, 'token': token})}"
    return {"ok": True, "uri": deep_link, "session_token": token}


@api.post("/guard/session/connect")
async def guard_session_connect(body: GuardConnectIn, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": body.match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    is_participant = user.get("clan_id") in (match.get("clan_a_id"), match.get("clan_b_id"))
    if (not is_participant) and (not is_staff(user)):
        raise HTTPException(403, "للأطراف المشاركة فقط")

    platform = _normalize_gaming_platform(body.platform or user.get("gaming_platform") or "pc")
    hwid_hash = (body.hwid_hash or "").strip()
    if hwid_hash:
        banned = await db.guard_hwid_bans.find_one({"hwid_hash": hwid_hash}, {"_id": 0, "id": 1})
        if banned:
            raise HTTPException(403, "هذا الجهاز محظور من المنصة")

    expected_token = (user.get("guard_session_token") or "").strip()
    incoming_token = (body.session_token or "").strip()
    if expected_token and incoming_token and incoming_token != expected_token:
        raise HTTPException(403, "رمز الربط غير صالح")

    if not expected_token:
        expected_token = incoming_token or secrets.token_urlsafe(24)
        await db.users.update_one({"id": user["id"]}, {"$set": {"guard_session_token": expected_token}})

    now_iso = iso(now_utc())
    await db.users.update_one({"id": user["id"]}, {"$set": {"gaming_platform": platform}})
    await db.guard_sessions.update_one(
        {"match_id": body.match_id, "user_id": user["id"]},
        {"$set": {
            "match_id": body.match_id,
            "user_id": user["id"],
            "username": user.get("username"),
            "platform": platform,
            "status": "active",
            "session_token": expected_token,
            "app_version": (body.app_version or "").strip(),
            "hwid_hash": hwid_hash,
            "last_seen_at": now_iso,
            "updated_at": now_iso,
        }, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now_iso}},
        upsert=True,
    )
    await _broadcast_guard_status(body.match_id)
    return {"ok": True, "status": "active", "session_token": expected_token}


@api.post("/guard/session/heartbeat")
async def guard_session_heartbeat(body: GuardHeartbeatIn, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": body.match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    session = await db.guard_sessions.find_one({"match_id": body.match_id, "user_id": user["id"]}, {"_id": 0})
    if not session:
        raise HTTPException(404, "جلسة الحماية غير موجودة")
    incoming_token = (body.session_token or "").strip()
    expected_token = (session.get("session_token") or "").strip()
    if expected_token and incoming_token and incoming_token != expected_token:
        raise HTTPException(403, "رمز الجلسة غير صحيح")

    await db.guard_sessions.update_one(
        {"id": session["id"]},
        {"$set": {"status": "active", "last_seen_at": iso(now_utc()), "updated_at": iso(now_utc())}},
    )
    await _broadcast_guard_status(body.match_id)
    return {"ok": True}


@api.post("/guard/session/disconnect")
async def guard_session_disconnect(body: GuardHeartbeatIn, user: dict = Depends(get_current_user)):
    await db.guard_sessions.update_one(
        {"match_id": body.match_id, "user_id": user["id"]},
        {"$set": {"status": "inactive", "updated_at": iso(now_utc())}},
    )
    await _broadcast_guard_status(body.match_id)
    return {"ok": True}


@api.post("/guard/alerts/upload")
async def guard_alert_upload(
    match_id: str = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    detection_type: str = Form("unknown"),
    severity: str = Form("high"),
    hwid_hash: str = Form(""),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    is_participant = user.get("clan_id") in (match.get("clan_a_id"), match.get("clan_b_id"))
    if (not is_participant) and (not is_staff(user)):
        raise HTTPException(403, "غير مصرح")

    original_name = (file.filename or "guard_package.zip").strip()
    if not original_name.lower().endswith(".zip"):
        raise HTTPException(400, "يجب رفع ملف ZIP فقط")

    saved_name = f"{uuid.uuid4()}.zip"
    out_path = GUARD_UPLOAD_DIR / saved_name
    total = 0
    try:
        with out_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > GUARD_ALERT_MAX_BYTES:
                    out.close()
                    out_path.unlink(missing_ok=True)
                    raise HTTPException(400, "حجم ملف الإثبات كبير جداً")
                out.write(chunk)
    finally:
        await file.close()

    alert_doc = {
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "reporter_user_id": user["id"],
        "reporter_username": user.get("username"),
        "severity": (severity or "high").strip().lower(),
        "detection_type": (detection_type or "unknown").strip().lower(),
        "title": (title or "Rivals Guard Alert").strip()[:180],
        "description": (description or "").strip()[:2000],
        "hwid_hash": (hwid_hash or "").strip(),
        "zip_file_name": saved_name,
        "zip_original_name": original_name,
        "zip_size": total,
        "zip_url": f"/api/uploads/guard/{saved_name}",
        "status": "open",
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    }
    await db.guard_alerts.insert_one(alert_doc)

    admins = await db.users.find({"role": {"$in": ["owner", "admin"]}}, {"_id": 0, "id": 1}).to_list(100)
    for adm in admins:
        await _create_notification(
            user_id=adm["id"],
            title="🚨 Red Alert: Rivals Guard",
            body=f"تنبيه أمني في مباراة {match_id} — {alert_doc['title']}",
            kind="guard_red_alert",
            data={"match_id": match_id, "alert_id": alert_doc["id"], "severity": alert_doc["severity"]},
        )

    await _guard_presence_hub.broadcast(match_id, {
        "event": "guard_red_alert",
        "match_id": match_id,
        "alert_id": alert_doc["id"],
        "title": alert_doc["title"],
        "severity": alert_doc["severity"],
        "status": "open",
    })

    return {"ok": True, "alert_id": alert_doc["id"], "zip_url": alert_doc["zip_url"]}


@api.get("/admin/guard/alerts")
async def admin_guard_alerts(user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    docs = await db.guard_alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(300)
    return docs


@api.delete("/admin/guard/alerts/{alert_id}")
async def admin_guard_delete_alert(alert_id: str, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    doc = await db.guard_alerts.find_one({"id": alert_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "غير موجود")
    zname = (doc.get("zip_file_name") or "").strip()
    if zname:
        (GUARD_UPLOAD_DIR / zname).unlink(missing_ok=True)
    await db.guard_alerts.delete_one({"id": alert_id})
    return {"ok": True}


@api.post("/admin/guard/hwid-ban")
async def admin_guard_hwid_ban(body: GuardHwidBanIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    h = (body.hwid_hash or "").strip()
    await db.guard_hwid_bans.update_one(
        {"hwid_hash": h},
        {"$set": {
            "hwid_hash": h,
            "reason": (body.reason or "").strip()[:600],
            "created_by_user_id": user["id"],
            "created_by_username": user.get("username"),
            "updated_at": iso(now_utc()),
        }, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": iso(now_utc())}},
        upsert=True,
    )
    return {"ok": True, "hwid_hash": h}


@api.websocket("/ws/matches/{match_id}/guard")
async def ws_match_guard_status(websocket: WebSocket, match_id: str):
    await _guard_presence_hub.connect(match_id, websocket)
    try:
        await websocket.send_json({"event": "connected", "match_id": match_id})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await _guard_presence_hub.disconnect(match_id, websocket)


@api.get("/matches/{match_id}/mvp-status")
async def get_match_mvp_status(match_id: str, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match.get("status") != "finished":
        return {"can_vote": False, "reason": "المباراة لم تنتهِ بعد"}
    match = await _ensure_mvp_voting_initialized(match)
    attendance_a = _eligible_attendance_ids(match, "A")
    attendance_b = _eligible_attendance_ids(match, "B")
    is_a = user["id"] in attendance_a
    is_b = user["id"] in attendance_b
    if not (is_a or is_b):
        return {"can_vote": False, "reason": "أنت لست ضمن قائمة التحضير لهذه المباراة"}
    own_pool = attendance_a if is_a else attendance_b
    teammate_ids = [uid for uid in own_pool if uid != user["id"]]
    vote = next((v for v in (match.get("mvp_votes") or []) if v.get("voter_id") == user["id"]), None)
    winner_id = match.get("mvp_winner_user_id")
    winner_user = None
    if winner_id:
        winner_user = await db.users.find_one({"id": winner_id}, {"_id": 0, "id": 1, "username": 1, "act": 1})
    teammates = await db.users.find(
        {"id": {"$in": teammate_ids}},
        {"_id": 0, "id": 1, "username": 1, "act": 1},
    ).to_list(100)
    return {
        "can_vote": vote is None and winner_id is None,
        "has_voted": vote is not None,
        "voted_for": vote.get("candidate_id") if vote else None,
        "eligible_teammates": teammates,
        "winner": winner_user,
        "total_votes": len(match.get("mvp_votes") or []),
    }


@api.post("/matches/{match_id}/mvp-vote")
async def vote_match_mvp(match_id: str, body: MvpVoteIn, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match.get("status") != "finished":
        raise HTTPException(400, "التصويت متاح بعد نهاية المباراة")
    match = await _ensure_mvp_voting_initialized(match)
    attendance_a = _eligible_attendance_ids(match, "A")
    attendance_b = _eligible_attendance_ids(match, "B")
    voter_id = user["id"]
    if voter_id in attendance_a:
        own_pool = attendance_a
        voter_clan = match.get("clan_a_id")
    elif voter_id in attendance_b:
        own_pool = attendance_b
        voter_clan = match.get("clan_b_id")
    else:
        raise HTTPException(403, "فقط اللاعبين المحضرين يمكنهم التصويت")
    if match.get("mvp_winner_user_id"):
        raise HTTPException(400, "تم إغلاق التصويت")
    if body.player_id == voter_id:
        raise HTTPException(400, "لا يمكنك التصويت لنفسك")
    if body.player_id not in own_pool:
        raise HTTPException(400, "يمكنك التصويت لزميلك فقط من قائمة التحضير")
    if any(v.get("voter_id") == voter_id for v in (match.get("mvp_votes") or [])):
        raise HTTPException(400, "لقد قمت بالتصويت بالفعل")
    vote_doc = {
        "voter_id": voter_id,
        "voter_clan_id": voter_clan,
        "candidate_id": body.player_id,
        "created_at": iso(now_utc()),
    }
    await db.matches.update_one({"id": match_id}, {"$push": {"mvp_votes": vote_doc}})
    fresh = await db.matches.find_one({"id": match_id}, {"_id": 0})
    winner_id = await _finalize_mvp_if_ready(fresh)
    return {
        "ok": True,
        "winner_user_id": winner_id,
        "total_votes": len((fresh or {}).get("mvp_votes") or []),
    }


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


async def _assert_guard_ready_for_live_ops(match: dict, user: dict) -> None:
    if not match or match.get("status") != "live":
        return
    if is_staff(user):
        return
    snapshot = await _resolve_guard_roster(match)
    if snapshot.get("all_pc_ready"):
        return
    raise HTTPException(423, "لا يمكن بدء/متابعة الجولة حتى تفعيل Rivals Guard لكل لاعبي PC")


@api.post("/matches/{match_id}/vote-map")
async def vote_map(match_id: str, body: MapVoteIn, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")
    await _assert_guard_ready_for_live_ops(match, user)
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
    won_a, won_b = _count_maps(fresh["maps"])
    if fresh["maps"][body.map_index].get("winner"):
        await _post_match_score_news(fresh, won_a, won_b)
    return await _enrich_match(fresh)


@api.post("/matches/{match_id}/admin-resolve-map")
async def admin_resolve_map(match_id: str, body: AdminResolveMapIn, request: Request, user: dict = Depends(get_current_user)):
    # Dispute resolution is allowed for full management team: owner + admins.
    if user.get("role") not in ("owner", "admin"):
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
    won_a, won_b = _count_maps(fresh["maps"])
    await _post_match_score_news(fresh, won_a, won_b)
    await _audit_admin_action(
        actor=user,
        action="match.admin_resolve_map",
        target_type="match",
        target_id=match_id,
        meta={"map_index": body.map_index, "winner_clan_id": body.winner_clan_id},
        request=request,
    )
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
    # Per-league standings (decoupled)
    m_doc = await db.matches.find_one({"id": match_id}, {"_id": 0, "league_id": 1})
    league_id = (m_doc or {}).get("league_id")
    if league_id:
        await _apply_league_standings(league_id, winning_clan, POINTS_WIN, win=True)
        await _apply_league_standings(league_id, withdrawing_clan, POINTS_WITHDRAW, loss=True)
    m_full = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if m_full:
        winner_side = "A" if winning_clan == m_full.get("clan_a_id") else "B"
        loser_side = "B" if winner_side == "A" else "A"
        winners = _eligible_attendance_ids(m_full, winner_side)
        losers = _eligible_attendance_ids(m_full, loser_side)
        if winners:
            await db.users.update_many({"id": {"$in": winners}}, {"$inc": {"wins": 1}})
        if losers:
            await db.users.update_many({"id": {"$in": losers}}, {"$inc": {"losses": 1}})
        await _ensure_mvp_voting_initialized(m_full)
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
    winner_clan_doc = await db.clans.find_one({"id": winning_clan}, {"_id": 0, "name": 1})
    withdrawing_doc = await db.clans.find_one({"id": withdrawing_clan}, {"_id": 0, "name": 1})
    if winner_clan_doc and withdrawing_doc:
        await _create_news_post(
            kind="match-final",
            title=f"نهاية المباراة بالانسحاب • فوز {winner_clan_doc['name']}",
            body=f"انسحب {withdrawing_doc['name']} من المباراة",
        )


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
    await _assert_guard_ready_for_live_ops(match, user)
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
    await _assert_guard_ready_for_live_ops(match, user)
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
    won_a, won_b = _count_maps(fresh["maps"])
    await _post_match_score_news(fresh, won_a, won_b)
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
    await _maybe_emit_zikr_alert_for_match(m)
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
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
    tactical_banner = None
    alert = (m or {}).get("zikr_alert") or {}
    if alert.get("window_ends_at"):
        try:
            if datetime.fromisoformat(alert["window_ends_at"]) > now_utc():
                tactical_banner = alert
        except Exception:
            tactical_banner = None
    return {
        "messages": filtered,
        "can_write": can_write,
        "user_clan_id": user_clan,
        "is_admin": is_admin,
        "tactical_banner": tactical_banner,
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


async def _insert_system_chat_message(match_id: str, text: str, username: str = "النظام") -> None:
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "user_id": "system",
        "username": username,
        "user_role": "admin" if username == "النظام" else "bot",
        "user_clan_id": None,
        "type": "text",
        "text": text,
        "image": None,
        "video": None,
        "opponent_decision": None,
        "admin_decision": None,
        "admin_note": "",
        "created_at": iso(now_utc()),
    })


async def _post_sanad_welcome(match_id: str) -> None:
    existing = await db.chat_messages.find_one(
        {"match_id": match_id, "user_id": "sanad-bot", "kind": "sanad_welcome"},
        {"_id": 0, "id": 1},
    )
    if existing:
        return
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "user_id": "sanad-bot",
        "username": "سند 🤖",
        "user_role": "bot",
        "user_clan_id": None,
        "type": "text",
        "kind": "sanad_welcome",
        "text": "أهلاً بكم يا أبطال! أنا البوت الذكي سند 🤖، أعرف كل تفاصيل المنصة وقوانينها وقادر على مساعدتكم. اكتبوا كلمة (سند) في الشات وسأكون معكم فوراً. أتمنى لكم التوفيق! 🚀",
        "image": None,
        "video": None,
        "opponent_decision": None,
        "admin_decision": None,
        "admin_note": "",
        "created_at": iso(now_utc()),
    })


def _sanad_answer(question: str) -> str:
    q = (question or "").strip().lower()
    if any(k in q for k in ["قانون", "rules", "نظام"]):
        return "📘 القوانين الرسمية موجودة في صفحة القوانين داخل المنصة. التزموا بنتيجة التصويت، واحفظوا لقطات الإثبات عند النزاع."
    if any(k in q for k in ["بريك", "صلاة", "prayer"]):
        return "🕌 بريك الصلاة يتفعّل بعد تنبيه ذِكْر فقط، ولفترة 15 دقيقة، ومرة واحدة لكل مباراة مع تأكيد الطرفين."
    if any(k in q for k in ["نقاط", "points", "ترتيب", "leaderboard"]):
        return "🏆 الفوز يعطي +3 نقاط، الخسارة -1، والانسحاب -3. الترتيب يتحدث تلقائياً بعد نهاية المباراة."
    if any(k in q for k in ["شات", "chat", "صورة", "فيديو"]):
        return "💬 القادة/النواب والمنظمون يقدرون يكتبون في شات المباراة. الوسائط تُراجع حسب النظام قبل اعتمادها عند الحاجة."
    return "🤖 حاضر! إذا سؤالك عن القوانين، التحديات، شات المباراة، أو نقاط الترتيب، اكتب سؤالك بشكل مختصر وواضح وسأجاوبك فوراً."


async def _maybe_handle_sanad_mention(match: dict, user: dict, text: str) -> None:
    raw = (text or "").strip()
    if not raw:
        return
    lowered = raw.lower()
    if ("سند" not in raw) and ("sanad" not in lowered):
        return

    await _send_sanad_reply(match.get("id"), user, raw)


async def _send_sanad_reply(match_id: str, user: dict, question: str) -> dict:
    answer = _sanad_answer(question)
    await db.sanad_questions.insert_one({
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "user_id": user.get("id"),
        "username": user.get("username"),
        "question": question,
        "answer": answer,
        "created_at": iso(now_utc()),
    })

    reply = {
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "user_id": "sanad-bot",
        "username": "سند 🤖",
        "user_role": "bot",
        "user_clan_id": None,
        "type": "text",
        "kind": "sanad_reply",
        "text": answer,
        "image": None,
        "video": None,
        "opponent_decision": None,
        "admin_decision": None,
        "admin_note": "",
        "created_at": iso(now_utc()),
    }
    await db.chat_messages.insert_one(reply)
    return reply


async def _maybe_emit_zikr_alert_for_match(match: dict) -> Optional[dict]:
    if not match or match.get("status") != "live":
        return None
    now = now_utc()
    existing = match.get("zikr_alert") or {}
    existing_window = existing.get("window_ends_at")
    if existing_window:
        try:
            if datetime.fromisoformat(existing_window) > now:
                return existing
        except Exception:
            pass

    participant_ids = _unique_ids((match.get("attendance_a_ids") or []) + (match.get("attendance_b_ids") or []))
    if not participant_ids:
        participant_ids = _unique_ids([match.get("clan_a_id"), match.get("clan_b_id")])
        clans = await db.clans.find({"id": {"$in": participant_ids}}, {"_id": 0, "leader_id": 1}).to_list(10)
        participant_ids = _unique_ids([c.get("leader_id") for c in clans])
    if not participant_ids:
        return None

    users = await db.users.find(
        {"id": {"$in": participant_ids}},
        {"_id": 0, "registration_city": 1, "registration_country": 1},
    ).to_list(200)
    seen_locs = []
    for u in users:
        city = (u.get("registration_city") or "").strip()
        country = (u.get("registration_country") or "Saudi Arabia").strip()
        if city:
            key = f"{city.lower()}::{country.lower()}"
            if key not in seen_locs:
                seen_locs.append(key)

    if not seen_locs:
        return None

    for loc in seen_locs[:3]:
        city, country = loc.split("::", 1)
        snap = await _fetch_prayer_snapshot(city, country)
        if not snap:
            continue
        tz_name = snap.get("timezone") or "Asia/Riyadh"
        try:
            local_now = now.astimezone(ZoneInfo(tz_name))
        except Exception:
            local_now = now.astimezone(timezone(timedelta(hours=3)))
        prayer_order = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        timings = snap.get("timings") or {}
        for p_name in prayer_order:
            hhmm = (timings.get(p_name) or "").strip()
            if not re.match(r"^\d{1,2}:\d{2}$", hhmm):
                continue
            hh, mm = [int(x) for x in hhmm.split(":", 1)]
            p_dt = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            elapsed = (local_now - p_dt).total_seconds()
            if 0 <= elapsed <= PRAYER_ALERT_WINDOW_SECONDS:
                prayer_ar = _prayer_name_ar(p_name)
                day_key = local_now.strftime("%Y-%m-%d")
                announce_key = f"{day_key}:{p_name}:{city}:{country}"
                if match.get("zikr_last_key") == announce_key:
                    return match.get("zikr_alert")
                text = f"﴿وَذَكِّرْ فَإِنَّ الذِّكْرَىٰ تَنفَعُ الْمُؤْمِنِينَ﴾ — حان الآن موعد أذان {prayer_ar} حسب توقيت مدينتكم. تقبل الله طاعتكم 🤍"
                window_ends_at = iso(now + timedelta(seconds=PRAYER_ALERT_WINDOW_SECONDS))
                alert_doc = {
                    "prayer_name": prayer_ar,
                    "message": text,
                    "issued_at": iso(now),
                    "window_ends_at": window_ends_at,
                    "city": city,
                    "country": country,
                }
                await db.matches.update_one(
                    {"id": match["id"]},
                    {"$set": {"zikr_alert": alert_doc, "zikr_last_key": announce_key}},
                )
                await _insert_system_chat_message(match["id"], text, username="ذِكْر 🤍")
                return alert_doc
    return None


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
    await _maybe_handle_sanad_mention(m, user, body.text or "")
    msg.pop("_id", None)
    # Fire-and-forget AI toxicity scan for text messages
    if msg.get("type") == "text" and (msg.get("text") or "").strip():
        asyncio.create_task(_ai_toxicity_check(
            match_id, msg["id"], user["id"], user["username"], msg["text"]
        ))
    return msg


class SanadAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@api.post("/matches/{match_id}/sanad/ask")
async def ask_sanad(match_id: str, body: SanadAskIn, user: dict = Depends(get_current_user)):
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")

    can_view_text, _, _, _, _ = await _chat_perms(match, user)
    if not can_view_text and not is_staff(user):
        raise HTTPException(403, "سند متاح فقط لأطراف المباراة")

    question = (body.question or "").strip()
    if not question:
        raise HTTPException(400, "السؤال فارغ")

    reply = await _send_sanad_reply(match_id, user, question)
    return {
        "ok": True,
        "question": question,
        "answer": reply.get("text") or "",
        "reply": reply,
    }


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


# ---------------- LEADERBOARD HELPERS (used by per-league standings + clan badges) ----------------
def _clan_is_plus(c: dict) -> bool:
    if c.get("is_plus"):
        return True
    until = c.get("plus_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > now_utc()
    except Exception:
        return False


def _clan_badges(c: dict) -> list:
    """Return compact badge dicts for the leaderboard UI."""
    out = []
    for t in c.get("trophies", []):
        out.append({
            "id": t.get("id"),
            "kind": t.get("kind"),
            "label": t.get("label"),
            "awarded_at": t.get("awarded_at"),
        })
    return out


@api.get("/leaderboard/clans")
async def leaderboard_clans():
    """Global clan leaderboard used by the homepage and standings screens."""
    clans = await db.clans.find(
        {"archived": {"$ne": True}},
        {"_id": 0, "id": 1, "name": 1, "tag": 1, "points": 1, "wins": 1, "losses": 1, "is_plus": 1, "plus_until": 1, "trophies": 1, "logo": 1, "logo_url": 1, "avatar": 1},
    ).sort([("points", -1), ("wins", -1), ("name", 1)]).to_list(500)
    out = []
    for c in clans:
        wins = int(c.get("wins") or 0)
        losses = int(c.get("losses") or 0)
        out.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "tag": c.get("tag"),
            "points": int(c.get("points") or 0),
            "wins": wins,
            "losses": losses,
            "kd": float(wins) if losses == 0 else round(wins / max(losses, 1), 2),
            "is_clan_plus": _clan_is_plus(c),
            "badges": _clan_badges(c),
            "logo": c.get("logo"),
            "logo_url": c.get("logo_url"),
            "avatar": c.get("avatar"),
        })
    return out


@api.get("/leaderboard/players")
async def leaderboard_players():
    """Global player leaderboard used by the homepage and standings screens."""
    users = await db.users.find(
        {"role": {"$ne": "owner"}},
        {"_id": 0, "id": 1, "username": 1, "wins": 1, "losses": 1, "points": 1, "personal_plus_until": 1, "is_plus": 1},
    ).sort([("points", -1), ("wins", -1), ("username", 1)]).to_list(1000)
    out = []
    for u in users:
        wins = int(u.get("wins") or 0)
        losses = int(u.get("losses") or 0)
        out.append({
            "id": u.get("id"),
            "username": u.get("username"),
            "points": int(u.get("points") or 0),
            "wins": wins,
            "losses": losses,
            "kd": float(wins) if losses == 0 else round(wins / max(losses, 1), 2),
            "is_personal_plus": user_is_personal_plus(u),
        })
    return out


# ---------------- DISCORD WEBHOOK (community notifications) ----------------
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()


async def _send_discord_embed(title: str, description: str, color: int = 0xFFCC00, fields: Optional[list] = None) -> None:
    """Fire-and-forget Discord webhook. Silent no-op when env var is missing."""
    if not DISCORD_WEBHOOK_URL:
        return
    import httpx
    payload = {
        "embeds": [{
            "title": title[:240],
            "description": description[:2000],
            "color": color,
            "timestamp": iso(now_utc()),
            "fields": fields or [],
            "footer": {"text": "RIVALS COD LEAGUE"},
        }]
    }
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            await c.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as exc:
        logger.warning(f"Discord webhook error: {exc}")


# ---------------- OWNER-ONLY: manual Plus grant/revoke ----------------
class PlusGrantIn(BaseModel):
    action: Literal["grant", "revoke"]
    days: int = Field(default=30, ge=1, le=3650)


@api.post("/admin/users/{user_id}/personal-plus")
async def owner_set_personal_plus(user_id: str, body: PlusGrantIn, request: Request, user: dict = Depends(get_current_user)):
    """Owner-only: grant or revoke Personal Plus instantly (bypasses payment)."""
    if not is_owner(user):
        raise HTTPException(403, "صلاحية المالك فقط")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "المستخدم غير موجود")
    if body.action == "grant":
        new_until = iso(now_utc() + timedelta(days=body.days))
        await db.users.update_one({"id": user_id}, {"$set": {"personal_plus_until": new_until}})
        await _create_notification(
            user_id=user_id,
            title="تم تفعيل Personal Plus",
            body=f"تم منحك اشتراك Personal Plus لمدة {body.days} يوم.",
            kind="plus",
            data={"action": "grant", "days": body.days, "personal_plus_until": new_until},
        )
        await _audit_admin_action(
            actor=user,
            action="plus.personal.update",
            target_type="user",
            target_id=user_id,
            meta={"action": body.action, "days": body.days, "personal_plus_until": new_until},
            request=request,
        )
        return {"ok": True, "personal_plus_until": new_until}
    await db.users.update_one({"id": user_id}, {"$set": {"personal_plus_until": None}})
    await _create_notification(
        user_id=user_id,
        title="تم إيقاف Personal Plus",
        body="تم إيقاف اشتراك Personal Plus لحسابك.",
        kind="plus",
        data={"action": "revoke"},
    )
    await _audit_admin_action(
        actor=user,
        action="plus.personal.update",
        target_type="user",
        target_id=user_id,
        meta={"action": body.action, "days": body.days, "personal_plus_until": None},
        request=request,
    )
    return {"ok": True, "personal_plus_until": None}


@api.post("/admin/clans/{clan_id}/plus")
async def owner_set_clan_plus(clan_id: str, body: PlusGrantIn, request: Request, user: dict = Depends(get_current_user)):
    """Owner-only: grant or revoke Clan Plus (sets the leader's plus_expires_at + flags clan)."""
    if not is_owner(user):
        raise HTTPException(403, "صلاحية المالك فقط")
    clan = await _get_clan(clan_id)
    if body.action == "grant":
        new_until = iso(now_utc() + timedelta(days=body.days))
        await db.clans.update_one(
            {"id": clan_id},
            {"$set": {"plus_until": new_until, "is_plus": True}},
        )
        await db.users.update_one(
            {"id": clan["leader_id"]},
            {"$set": {"plus_expires_at": new_until}},
        )
        await _create_notification(
            user_id=clan["leader_id"],
            title="تم تفعيل Clan Plus",
            body=f"تم تفعيل Clan Plus لكلانك لمدة {body.days} يوم.",
            kind="plus",
            data={"action": "grant", "days": body.days, "clan_id": clan_id, "plus_until": new_until},
        )
        await _audit_admin_action(
            actor=user,
            action="plus.clan.update",
            target_type="clan",
            target_id=clan_id,
            meta={"action": body.action, "days": body.days, "plus_until": new_until},
            request=request,
        )
        return {"ok": True, "plus_until": new_until}
    await db.clans.update_one(
        {"id": clan_id},
        {"$set": {"plus_until": None, "is_plus": False}},
    )
    await _create_notification(
        user_id=clan["leader_id"],
        title="تم إيقاف Clan Plus",
        body="تم إيقاف Clan Plus لكلانك.",
        kind="plus",
        data={"action": "revoke", "clan_id": clan_id},
    )
    await _audit_admin_action(
        actor=user,
        action="plus.clan.update",
        target_type="clan",
        target_id=clan_id,
        meta={"action": body.action, "days": body.days, "plus_until": None},
        request=request,
    )
    return {"ok": True, "plus_until": None}


# ---------------- HEAD-TO-HEAD (clan rivalry record) ----------------
@api.get("/matches/{match_id}/h2h")
async def head_to_head(match_id: str):
    """Returns lifetime H2H record between the two clans of this match."""
    m = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "غير موجود")
    a_id, b_id = m["clan_a_id"], m["clan_b_id"]
    pair = {"$or": [
        {"clan_a_id": a_id, "clan_b_id": b_id},
        {"clan_a_id": b_id, "clan_b_id": a_id},
    ], "status": "finished"}
    docs = await db.matches.find(pair, {"_id": 0, "winner_clan_id": 1, "finished_at": 1}).sort("finished_at", -1).to_list(200)
    a_wins = sum(1 for d in docs if d.get("winner_clan_id") == a_id)
    b_wins = sum(1 for d in docs if d.get("winner_clan_id") == b_id)
    a = await db.clans.find_one({"id": a_id}, {"_id": 0, "name": 1, "tag": 1, "id": 1})
    b = await db.clans.find_one({"id": b_id}, {"_id": 0, "name": 1, "tag": 1, "id": 1})
    return {
        "clan_a": a, "clan_b": b,
        "a_wins": a_wins, "b_wins": b_wins,
        "total": len(docs),
        "last_match_at": docs[0]["finished_at"] if docs else None,
    }


# ---------------- RULES ----------------
def _normalize_rule_doc(rule: dict) -> dict:
    images = rule.get("images")
    if not isinstance(images, list):
        images = []
    images = [img for img in images if isinstance(img, str) and img.strip()]

    legacy_image = rule.get("image")
    if isinstance(legacy_image, str) and legacy_image.strip() and legacy_image not in images:
        images.insert(0, legacy_image)

    rule["images"] = images
    rule["image"] = images[0] if images else ""
    return rule


@api.get("/rules")
async def list_rules():
    docs = await db.rules.find({}, {"_id": 0}).sort("order", 1).to_list(100)
    return [_normalize_rule_doc(d) for d in docs]


@api.post("/rules")
async def create_rule(body: RuleIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    payload = _normalize_rule_doc(body.model_dump())
    rule = {"id": str(uuid.uuid4()), **payload, "created_at": iso(now_utc())}
    await db.rules.insert_one(rule)
    rule.pop("_id", None)
    return rule


@api.put("/rules/{rule_id}")
async def update_rule(rule_id: str, body: RuleIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    payload = _normalize_rule_doc(body.model_dump())
    await db.rules.update_one({"id": rule_id}, {"$set": payload})
    r = await db.rules.find_one({"id": rule_id}, {"_id": 0})
    return _normalize_rule_doc(r) if r else None


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


@api.get("/admin/sanad-analytics")
async def admin_sanad_analytics(user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")

    total_questions = await db.sanad_questions.count_documents({})
    today_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    today_iso = iso(today_start)
    questions_today = await db.sanad_questions.count_documents({"created_at": {"$gte": today_iso}})

    top_matches_raw = await db.sanad_questions.aggregate([
        {"$group": {"_id": "$match_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]).to_list(5)

    top_users_raw = await db.sanad_questions.aggregate([
        {
            "$group": {
                "_id": {"$ifNull": ["$user_id", "$asked_by_user_id"]},
                "count": {"$sum": 1},
                "username": {"$last": {"$ifNull": ["$username", "$asked_by_username"]}},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]).to_list(5)

    latest = await db.sanad_questions.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)

    return {
        "total_questions": int(total_questions),
        "questions_today": int(questions_today),
        "top_matches": [
            {"match_id": t.get("_id"), "count": int(t.get("count", 0))}
            for t in top_matches_raw
            if t.get("_id")
        ],
        "top_users": [
            {"user_id": t.get("_id"), "username": t.get("username") or "-", "count": int(t.get("count", 0))}
            for t in top_users_raw
            if t.get("_id")
        ],
        "latest_questions": latest,
    }


@api.post("/admin/users/{user_id}/role")
async def change_user_role(user_id: str, body: RoleChangeIn, request: Request, user: dict = Depends(get_current_user)):
    if not is_owner(user):
        raise HTTPException(403, "للمالك فقط")
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "المستخدم غير موجود")
    if target.get("role") == "owner":
        raise HTTPException(400, "لا يمكن تغيير دور المالك")
    await db.users.update_one({"id": user_id}, {"$set": {"role": body.role}})
    await _create_notification(
        user_id=user_id,
        title="تم تحديث دور حسابك",
        body=f"تم تغيير دورك إلى {body.role}.",
        kind="account",
        data={"role": body.role},
    )
    await _audit_admin_action(
        actor=user,
        action="user.role.change",
        target_type="user",
        target_id=user_id,
        meta={"old_role": target.get("role"), "new_role": body.role},
        request=request,
    )
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
        await _post_sanad_welcome(m["id"])
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


def _champion_clan_info(clans_by_id: dict, clan_id: Optional[str], fallback_name: str = "كلان غير معروف") -> dict:
    clan = clans_by_id.get(clan_id) if clan_id else None
    if clan:
        return {
            "id": clan.get("id"),
            "name": clan.get("name") or fallback_name,
            "tag": clan.get("tag") or "---",
            "is_plus": bool(clan.get("is_plus")),
        }
    return {
        "id": clan_id,
        "name": fallback_name,
        "tag": "---",
        "is_plus": False,
    }


@api.get("/champions-factory")
@api.get("/results/champions")
@api.get("/champions")
async def champions_factory(
    q: Optional[str] = Query(default=None, description="Search by clan name/tag or event name"),
    limit: int = Query(default=200, ge=20, le=500, description="Max results per section"),
):
    """Return finished tournament and league champions for the Champions Factory page.

    The frontend can consume this as a single endpoint instead of composing multiple
    collections client-side.
    """
    clans = await db.clans.find(
        {},
        {"_id": 0, "id": 1, "name": 1, "tag": 1, "is_plus": 1}
    ).to_list(1000)
    clans_by_id = {c["id"]: c for c in clans if c.get("id")}

    q_text = (q or "").strip()
    q_regex = {"$regex": re.escape(q_text), "$options": "i"} if q_text else None

    tournament_query: dict = {"champion_clan_id": {"$ne": None}}
    if q_regex:
        tournament_query["$or"] = [
            {"name": q_regex},
            {"description": q_regex},
            {"rules": q_regex},
            {"champion_clan_name": q_regex},
        ]

    league_query: dict = {"champion_clan_id": {"$ne": None}}
    if q_regex:
        league_query["$or"] = [
            {"name": q_regex},
            {"description": q_regex},
            {"rules": q_regex},
            {"key": q_regex},
            {"champion_clan_name": q_regex},
        ]

    tournament_docs = await db.tournaments.find(
        tournament_query,
        {"_id": 0},
    ).sort([("finished_at", -1), ("created_at", -1)]).to_list(limit)

    league_docs = await db.leagues.find(
        league_query,
        {"_id": 0},
    ).sort([("finished_at", -1), ("started_at", -1)]).to_list(limit)

    tournaments = []
    for t in tournament_docs:
        finished_at = t.get("finished_at") or t.get("starts_at") or t.get("created_at")
        clan = _champion_clan_info(clans_by_id, t.get("champion_clan_id"), t.get("champion_clan_name") or "كلان غير معروف")
        event_name = t.get("name") or "بطولة غير مسماة"
        event_meta = t.get("description") or t.get("rules") or "بطولة مكتملة"

        if q_text:
            haystack = " ".join([
                str(event_name),
                str(event_meta),
                str(clan.get("name") or ""),
                str(clan.get("tag") or ""),
            ]).lower()
            if q_text.lower() not in haystack:
                continue

        tournaments.append({
            "id": t.get("id"),
            "event_name": event_name,
            "event_meta": event_meta,
            "status_label": "بطولة مكتملة" if t.get("status") == "finished" else "بطولة جارية",
            "date_label": finished_at,
            "badge_label": "Double Elimination" if t.get("losers_bracket") else "Single Elimination",
            "detail_left": f"عدد المشاركين: {len(t.get('participants') or [])}",
            "detail_right": f"الحامل الرسمي: {clan['name']}",
            "sort_key": finished_at or "",
            "clan": clan,
        })

    leagues = []
    for l in league_docs:
        finished_at = l.get("finished_at") or l.get("started_at")
        clan = _champion_clan_info(clans_by_id, l.get("champion_clan_id"), l.get("champion_clan_name") or "كلان غير معروف")
        event_name = l.get("name") or "دوري غير مسمى"
        event_meta = l.get("description") or l.get("rules") or "دوري مكتمل"

        if q_text:
            haystack = " ".join([
                str(event_name),
                str(event_meta),
                str(clan.get("name") or ""),
                str(clan.get("tag") or ""),
            ]).lower()
            if q_text.lower() not in haystack:
                continue

        leagues.append({
            "id": l.get("id"),
            "event_name": event_name,
            "event_meta": event_meta,
            "status_label": "دوري مكتمل" if l.get("status") == "finished" else "دوري نشط",
            "date_label": finished_at,
            "badge_label": l.get("key") or "League",
            "detail_left": f"بدأ في {l.get('started_at')}" if l.get("started_at") else "",
            "detail_right": f"البطل: {clan['name']}",
            "sort_key": finished_at or "",
            "clan": clan,
        })

    return {
        "tournaments": tournaments,
        "leagues": leagues,
        "counts": {
            "tournaments": len(tournaments),
            "leagues": len(leagues),
            "total": len(tournaments) + len(leagues),
        },
    }


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
    # Discord notification (fire-and-forget)
    asyncio.create_task(_send_discord_embed(
        title=f"🏆 بطولة جديدة مفتوحة للتسجيل: {body.name}",
        description=f"{body.description or ''}\n\n**عدد الكلانات:** {body.max_participants}\n**24 ساعة الأولى:** Plus فقط",
        color=0xFFCC00,
    ))
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
    _assert_clan_not_suspended(clan)
    await _assert_min_members_for_competitions(clan)
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
async def create_banner(body: BannerIn, request: Request, user: dict = Depends(get_current_user)):
    _rate_limit_or_429(request, "upload:banners", limit=25, window_seconds=10 * 60)
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    b = {"id": str(uuid.uuid4()), **body.model_dump(), "created_at": iso(now_utc())}
    await db.banners.insert_one(b)
    b.pop("_id", None)
    return b


@api.put("/banners/{bid}")
async def update_banner(bid: str, body: BannerIn, request: Request, user: dict = Depends(get_current_user)):
    _rate_limit_or_429(request, "upload:banners", limit=25, window_seconds=10 * 60)
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
async def upload_video(request: Request, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload a video file to disk; returns the URL. Limit depends on Plus."""
    _rate_limit_or_429(request, "upload:video", limit=15, window_seconds=10 * 60)
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
    if body.gaming_platform is not None:
        update["gaming_platform"] = (body.gaming_platform or "pc").strip().lower()
    if body.discord_username is not None:
        raw_du = (body.discord_username or "").strip()
        normalized_du = raw_du[1:] if raw_du.startswith("@") else raw_du
        if normalized_du and len(normalized_du) < 2:
            raise HTTPException(400, "Discord Username قصير جدا")
        if len(normalized_du) > 50:
            raise HTTPException(400, "Discord Username طويل جدا")
        update["discord_username"] = normalized_du
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
    for field in ("twitch_url", "kick_url", "youtube_url", "tiktok_url", "instagram_link", "x_link"):
        val = getattr(body, field)
        if val is None:
            continue
        val = val.strip()
        if val and not _is_url(val):
            raise HTTPException(400, f"رابط {field} غير صالح")
        update[field] = val
    # Personal Plus gated visual customization
    visual_fields = {
        "avatar": body.avatar,
        "banner": body.banner,
        "accent_color": body.accent_color,
    }
    wants_visual = any(v is not None for v in visual_fields.values())
    if wants_visual and not user_is_personal_plus(user):
        raise HTTPException(403, "تخصيص الصورة والبانر واللون متاح لمشتركي Personal Plus فقط")
    AVATAR_MAX = 2_000_000
    BANNER_MAX = 3_000_000
    HEX_RE = "#"
    if body.avatar is not None:
        v = body.avatar.strip()
        if v and not v.startswith("http"):
            if not v.startswith("data:image/"):
                raise HTTPException(400, "صيغة الصورة غير صحيحة")
            if len(v) > AVATAR_MAX * 1.4:
                raise HTTPException(400, "حجم الصورة كبير (الحد 2MB)")
            # PIL deep-validation: verify bytes are a real image and allow GIF
            try:
                _hdr, _b64 = v.split(",", 1)
                raw_bytes = base64.b64decode(_b64 + "==")  # lenient padding
                img_obj = PILImage.open(io.BytesIO(raw_bytes))
                img_fmt = (img_obj.format or "").upper()
                _ALLOWED_AVATAR_FMTS = {"JPEG", "PNG", "GIF", "WEBP"}
                if img_fmt not in _ALLOWED_AVATAR_FMTS:
                    raise HTTPException(
                        400,
                        f"صيغة الصورة غير مدعومة ({img_fmt}). المسموح: JPEG, PNG, GIF, WEBP",
                    )
                img_obj.verify()  # raises if corrupted
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(400, "الصورة تالفة أو غير صالحة")
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
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").strip("/")
        for h in hosts:
            h = (h or "").lower().strip("/")
            if not h:
                continue
            if host == h or host.endswith(f".{h}"):
                if not path:
                    return None
                head = path.split("/", 1)[0].strip()
                if head.startswith("@"):
                    head = head[1:]
                return head or None
        return None
    except Exception:
        return None


async def _youtube_live_info(url: str) -> Optional[dict]:
    """Best-effort check for YouTube live status from /live page response markers."""
    if not url:
        return None
    import httpx

    normalized_url = url.strip()
    if not _is_url(normalized_url):
        return None

    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get(normalized_url)
            if r.status_code != 200:
                return None
            text = r.text or ""
            text_l = text.lower()
            live_markers = (
                '"islivecontent":true',
                '"islive":true',
                "hqdefault_live.jpg",
                "ytlivebroadcast",
            )
            if not any(m in text_l for m in live_markers):
                return None

            final_url = str(r.url)
            title = ""
            m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', text, re.IGNORECASE)
            if m:
                title = m.group(1).strip()

            return {
                "platform": "youtube",
                "live": True,
                "title": title,
                "viewer_count": None,
                "thumbnail": "",
                "url": final_url or normalized_url,
            }
    except Exception as exc:
        logger.warning(f"YouTube live check error: {exc}")
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
    result = {"twitch": None, "kick": None, "youtube": None, "tiktok": None}
    th = _extract_handle(u.get("twitch_url", ""), ["twitch.tv"])
    kh = _extract_handle(u.get("kick_url", ""), ["kick.com"])
    youtube_url = (u.get("youtube_url") or "").strip()
    if th:
        result["twitch"] = await _twitch_live_info(th)
    if kh:
        result["kick"] = await _kick_live_info(kh)
    if youtube_url:
        result["youtube"] = await _youtube_live_info(youtube_url)
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
         "$or": [{"twitch_url": {"$ne": ""}}, {"kick_url": {"$ne": ""}}, {"youtube_url": {"$ne": ""}}]},
        {"_id": 0},
    ).to_list(200)
    streams = []
    for u in docs:
        twitch_handle = _extract_handle(u.get("twitch_url", ""), ["twitch.tv"])
        kick_handle = _extract_handle(u.get("kick_url", ""), ["kick.com"])
        checks: list[Optional[dict]] = []
        if twitch_handle:
            checks.append(await _twitch_live_info(twitch_handle))
        if kick_handle:
            checks.append(await _kick_live_info(kick_handle))
        if (u.get("youtube_url") or "").strip():
            checks.append(await _youtube_live_info(u.get("youtube_url")))

        for v in checks:
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
    for member_id in member_ids:
        await _discord_enqueue_clan_role_sync_member(user_id=member_id, old_clan_id=clan_id, new_clan_id="")
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
    restored = await db.clans.find_one({"id": clan_id}, {"_id": 0})
    if restored:
        await _discord_enqueue_clan_role_create(restored)
    await _discord_enqueue_clan_role_sync_member(user_id=clan["leader_id"], old_clan_id="", new_clan_id=clan_id)
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
    for c in clans:
        c["isPlusClan"] = bool(c.get("isPlusClan") or _clan_is_plus(c))
        c["attendance"] = await _clan_attendance_summary(c)
    return clans


# ---------------- MATCH-LEVEL PRAYER BREAK (15-min chat-side pause) ----------------
@api.post("/matches/{match_id}/match-prayer-break")
async def start_match_prayer_break(match_id: str, user: dict = Depends(get_current_user)):
    """Prayer break gate: opens only after Zikr prayer alert, one use per match.
    Requires both team captains (A+B) approvals to activate."""
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    if match["status"] != "live":
        raise HTTPException(400, "المباراة منتهية")

    await _maybe_emit_zikr_alert_for_match(match)
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})

    alert = (match or {}).get("zikr_alert") or {}
    alert_window_ok = False
    if alert.get("window_ends_at"):
        try:
            alert_window_ok = datetime.fromisoformat(alert["window_ends_at"]) > now_utc()
        except Exception:
            alert_window_ok = False
    if not alert_window_ok and not is_staff(user):
        raise HTTPException(400, "زر بريك الصلاة متاح فقط بعد تنبيه ذِكْر ولمدة 15 دقيقة")

    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    side = _user_side(user, a, b)
    if not side and not is_staff(user):
        raise HTTPException(403, "للقادة والنواب فقط")

    existing = (match.get("match_prayer_break") or {}).copy()
    if existing.get("used_once"):
        raise HTTPException(400, "تم استخدام بريك الصلاة سابقاً في هذه المباراة")

    existing_status = (existing.get("status") or "").lower()
    if existing_status == "active" and existing.get("ends_at"):
        try:
            if datetime.fromisoformat(existing["ends_at"]) > now_utc() and not existing.get("resumed"):
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

    if is_staff(user):
        pb = {
            "status": "active",
            "started_at": iso(now),
            "ends_at": iso(now + timedelta(seconds=MATCH_PRAYER_BREAK_SECONDS)),
            "started_by_clan": side or "ADMIN",
            "started_by_user_id": user["id"],
            "started_by_username": user["username"],
            "approved_by_sides": ["A", "B"],
            "ready_by_sides": [],
            "used_once": True,
            "resumed": False,
        }
        await db.matches.update_one({"id": match_id}, {"$set": {"match_prayer_break": pb}})
        await _insert_system_chat_message(match_id, "🕌 بدأ بريك الصلاة (15 دقيقة) — توقف اللعب", username="النظام")
        return pb

    pb = existing if existing else {
        "status": "pending",
        "requested_at": iso(now),
        "requested_by_side": side,
        "requested_by_user_id": user["id"],
        "requested_by_username": user["username"],
        "approved_by_sides": [],
        "ready_by_sides": [],
        "used_once": False,
        "resumed": False,
    }
    approved = _unique_ids(pb.get("approved_by_sides", []))
    if side not in approved:
        approved.append(side)
    pb["approved_by_sides"] = approved

    if len(approved) >= 2:
        pb["status"] = "active"
        pb["started_at"] = iso(now)
        pb["ends_at"] = iso(now + timedelta(seconds=MATCH_PRAYER_BREAK_SECONDS))
        pb["started_by_clan"] = pb.get("requested_by_side") or side
        pb["used_once"] = True
        pb["resumed"] = False
        pb["ready_by_sides"] = []
        await db.matches.update_one({"id": match_id}, {"$set": {"match_prayer_break": pb}})
        await _insert_system_chat_message(match_id, "🕌 تم اعتماد بريك الصلاة من الطرفين — توقف اللعب لمدة 15 دقيقة", username="النظام")
    else:
        pb["status"] = "pending"
        await db.matches.update_one({"id": match_id}, {"$set": {"match_prayer_break": pb}})

    await db.matches.update_one({"id": match_id}, {"$set": {"match_prayer_break": pb}})
    # Set per-user cooldown so the same user can't spam another prayer break for 30 min
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"prayer_break_cooldown_until": iso(now + timedelta(minutes=PRAYER_BREAK_USER_COOLDOWN_MIN))}},
    )
    return pb


@api.post("/matches/{match_id}/match-prayer-resume")
async def resume_match_prayer_break(match_id: str, user: dict = Depends(get_current_user)):
    """Ready-check resume: both teams must mark ready (or staff override) before resuming."""
    match = await db.matches.find_one({"id": match_id}, {"_id": 0})
    if not match:
        raise HTTPException(404, "غير موجود")
    pb = (match.get("match_prayer_break") or {}).copy()
    if not pb:
        raise HTTPException(400, "لا يوجد بريك صلاة جارٍ")
    if (pb.get("status") or "") != "active":
        raise HTTPException(400, "بريك الصلاة غير مفعل بعد")
    a = await _get_clan(match["clan_a_id"])
    b = await _get_clan(match["clan_b_id"])
    side = _user_side(user, a, b)

    if is_staff(user):
        pb["resumed"] = True
        pb["resumed_at"] = iso(now_utc())
        pb["ends_at"] = iso(now_utc())
        pb["status"] = "resumed"
        await db.matches.update_one({"id": match_id}, {"$set": {"match_prayer_break": pb}})
        await _insert_system_chat_message(match_id, "▶️ تم إنهاء بريك الصلاة بواسطة الإدارة — استئناف المباراة", username="النظام")
        return pb

    if side not in {"A", "B"}:
        raise HTTPException(403, "فقط قادة طرفي المباراة")

    ready = _unique_ids(pb.get("ready_by_sides", []))
    if side not in ready:
        ready.append(side)
    pb["ready_by_sides"] = ready

    if len(ready) >= 2:
        pb["resumed"] = True
        pb["resumed_at"] = iso(now_utc())
        pb["ends_at"] = iso(now_utc())
        pb["status"] = "resumed"
        await db.matches.update_one({"id": match_id}, {"$set": {"match_prayer_break": pb}})
        await _insert_system_chat_message(match_id, "✅ الفريقان أكدا الجاهزية — استئناف المباراة", username="النظام")
    else:
        await db.matches.update_one({"id": match_id}, {"$set": {"match_prayer_break": pb}})

    return pb


# ---------------- ADMIN: edit users / clans, forgot-password ----------------
@api.put("/admin/users/{user_id}")
async def admin_edit_user(user_id: str, body: AdminUserEditIn, request: Request, user: dict = Depends(get_current_user)):
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
        await _audit_admin_action(
            actor=user,
            action="user.edit",
            target_type="user",
            target_id=user_id,
            meta={"fields": sorted(list(update.keys()))},
            request=request,
        )
    fresh = await db.users.find_one({"id": user_id}, {"_id": 0})
    return sanitize_user(fresh)


@api.put("/admin/clans/{clan_id}")
async def admin_edit_clan(clan_id: str, body: AdminClanEditIn, request: Request, user: dict = Depends(get_current_user)):
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
        await _audit_admin_action(
            actor=user,
            action="clan.edit",
            target_type="clan",
            target_id=clan_id,
            meta={"fields": sorted(list(update.keys()))},
            request=request,
        )
    fresh = await db.clans.find_one({"id": clan_id}, {"_id": 0})
    return fresh


@api.post("/admin/clans/{clan_id}/suspend")
async def admin_suspend_clan(clan_id: str, body: ClanSuspendIn, request: Request, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    await _get_clan(clan_id)
    now = now_utc()
    until = now + timedelta(hours=body.hours)
    await db.clans.update_one(
        {"id": clan_id},
        {
            "$set": {
                "suspended_at": iso(now),
                "suspended_until": iso(until),
                "suspension_reason": (body.reason or "").strip(),
                "suspended_by": user["id"],
                "suspended_by_username": user.get("username", ""),
            }
        },
    )
    clan = await db.clans.find_one({"id": clan_id}, {"_id": 0, "leader_id": 1, "name": 1})
    if clan and clan.get("leader_id"):
        await _create_notification(
            user_id=clan["leader_id"],
            title="تم إيقاف الكلان مؤقتاً",
            body=f"تم تعليق كلانك لمدة {body.hours} ساعة. السبب: {(body.reason or '').strip() or 'غير محدد'}",
            kind="moderation",
            data={"clan_id": clan_id, "hours": body.hours},
        )
    await _audit_admin_action(
        actor=user,
        action="clan.suspend",
        target_type="clan",
        target_id=clan_id,
        meta={"hours": body.hours, "reason": (body.reason or "").strip()},
        request=request,
    )
    fresh = await db.clans.find_one({"id": clan_id}, {"_id": 0})
    fresh["suspension_remaining_seconds"] = _clan_suspension_remaining_seconds(fresh)
    fresh["suspension_active"] = fresh["suspension_remaining_seconds"] > 0
    return fresh


@api.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordIn):
    """Sends password reset OTP to user's email (if account exists)."""
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    # Always return 200 so as not to leak account existence
    if user:
        await _create_email_otp(
            purpose="reset_password",
            email=email,
            payload={"user_id": user["id"]},
            user_id=user["id"],
        )
    return {"ok": True, "message": "إن وُجد الحساب، تم إرسال رمز التحقق إلى البريد الإلكتروني"}


@api.post("/auth/reset-password")
async def reset_password(body: ResetPasswordIn):
    email = body.email.lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        # Keep response generic and avoid leaking account existence
        return {"ok": True, "message": "تم تحديث كلمة المرور بنجاح"}

    await _verify_email_otp("reset_password", email, body.otp, user_id=user["id"])

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_pw(body.new_password), "updated_at": iso(now_utc())}},
    )
    await db.auth_sessions.update_many(
        {"user_id": user["id"], "revoked_at": None},
        {"$set": {"revoked_at": iso(now_utc()), "revoked_reason": "password_reset"}},
    )
    return {"ok": True, "message": "تم تحديث كلمة المرور بنجاح"}


@api.get("/admin/password-resets")
async def admin_list_resets(user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    docs = await db.password_resets.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs


@api.post("/admin/password-resets/{rid}/complete")
async def admin_complete_reset(rid: str, request: Request, user: dict = Depends(get_current_user)):
    """Mark a reset request as 'sent/completed' once admin emails the user the link manually."""
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    await db.password_resets.update_one(
        {"id": rid}, {"$set": {"status": "completed", "completed_at": iso(now_utc())}}
    )
    await _audit_admin_action(
        actor=user,
        action="password_reset.complete",
        target_type="password_reset",
        target_id=rid,
        request=request,
    )
    return {"ok": True}


# ---------------- BLACKLIST (cheaters log) ----------------
@api.get("/blacklist")
async def list_blacklist():
    """PUBLIC list of blacklisted cheaters — anyone can view, only staff can mutate."""
    docs = await db.blacklist.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@api.post("/blacklist")
async def add_blacklist(body: BlacklistIn, request: Request, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    target_account = None
    if body.player_user_id:
        u = await db.users.find_one({"id": body.player_user_id}, {"_id": 0})
        if u:
            target_account = sanitize_user(u)
    created_at_dt = now_utc()
    ban_expires_at_dt = _one_year_later(created_at_dt)

    if target_account:
        await db.users.update_one(
            {"id": target_account["id"]},
            {
                "$set": {
                    "status": "Banned",
                    "banned_at": iso(created_at_dt),
                    "banned_until": iso(ban_expires_at_dt),
                    "ban_reason": "blacklist",
                }
            },
        )
        await _discord_enqueue_moderation_sync(
            user_id=target_account["id"],
            action="ban",
            reason="blacklist",
            until=iso(ban_expires_at_dt),
            warning_points=0,
        )
        # Refresh projected account snapshot for blacklist record
        fresh = await db.users.find_one({"id": target_account["id"]}, {"_id": 0})
        if fresh:
            target_account = sanitize_user(fresh)

    entry = {
        "id": str(uuid.uuid4()),
        "player_name": body.player_name,
        "player_user_id": body.player_user_id,
        "player_email": body.player_email or (target_account or {}).get("email", ""),
        "player_account": target_account,
        "ban_applied": bool(target_account),
        "ban_expires_at": iso(ban_expires_at_dt) if target_account else None,
        "cheat_tool": body.cheat_tool,
        "details": body.details or "",
        "proof_image": body.proof_image or "",
        "added_by": user["id"],
        "added_by_username": user["username"],
        "created_at": iso(created_at_dt),
    }
    await db.blacklist.insert_one(entry)
    if target_account and target_account.get("id"):
        await _create_notification(
            user_id=target_account["id"],
            title="تم حظر حسابك",
            body="تم إدراج حسابك في القائمة السوداء لمدة سنة.",
            kind="moderation",
            data={"reason": "blacklist", "ban_expires_at": entry.get("ban_expires_at")},
        )
    await _audit_admin_action(
        actor=user,
        action="blacklist.add",
        target_type="blacklist",
        target_id=entry["id"],
        meta={
            "player_user_id": body.player_user_id,
            "player_name": body.player_name,
            "cheat_tool": body.cheat_tool,
        },
        request=request,
    )
    entry.pop("_id", None)
    return entry


@api.delete("/blacklist/{bid}")
async def remove_blacklist(bid: str, request: Request, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    existing = await db.blacklist.find_one({"id": bid}, {"_id": 0, "player_user_id": 1})
    await db.blacklist.delete_one({"id": bid})
    target_user_id = (existing or {}).get("player_user_id")
    if target_user_id:
        await _discord_enqueue_moderation_sync(
            user_id=str(target_user_id),
            action="unban",
            reason="blacklist_remove",
            until="",
            warning_points=0,
        )
    await _audit_admin_action(
        actor=user,
        action="blacklist.remove",
        target_type="blacklist",
        target_id=bid,
        request=request,
    )
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


async def _top_league_clan_ids(league_id: str, limit: int = 4) -> List[str]:
    """Top clans for a league based on league standings, then joined clans fallback."""
    top_rows = await db.league_standings.find(
        {"league_id": league_id}, {"_id": 0, "clan_id": 1}
    ).sort([("points", -1), ("wins", -1)]).to_list(limit)

    ids: List[str] = []
    seen = set()

    for row in top_rows:
        cid = row.get("clan_id")
        if cid and cid not in seen:
            seen.add(cid)
            ids.append(cid)

    if len(ids) < limit:
        joined = await db.clans.find(
            {
                "league_ids": league_id,
                "archived": {"$ne": True},
                "id": {"$nin": ids},
            },
            {"_id": 0, "id": 1},
        ).sort([("points", -1), ("wins", -1)]).to_list(limit)
        for c in joined:
            cid = c.get("id")
            if cid and cid not in seen:
                seen.add(cid)
                ids.append(cid)
            if len(ids) >= limit:
                break

    return ids[:limit]


async def _create_super_rivals_tournament_from_league(league: dict, created_by: Optional[str] = None) -> Optional[dict]:
    """Create one auto tournament per completed league with top-4 clans.

    - Name: بطولة السوبر رايفلز - [Current Arabic Month]
    - Format: خروج مغلوب (single elimination)
    - Participants: top 4 clans from league standings
    """
    if not league or not league.get("id"):
        return None

    if not bool(league.get("super_rivals_enabled", False)):
        return None

    existing = await db.tournaments.find_one({"source_league_id": league["id"]}, {"_id": 0})
    if existing:
        await db.leagues.update_one(
            {"id": league["id"]},
            {
                "$set": {
                    "super_rivals_tournament_id": existing["id"],
                    "super_rivals_tournament_name": existing.get("name"),
                }
            },
        )
        return existing

    participants = await _top_league_clan_ids(league["id"], limit=4)
    now = now_utc()
    month_name = _ARABIC_MONTHS[now.month - 1]
    t_name = f"بطولة السوبر رايفلز - {month_name}"

    tournament = {
        "id": str(uuid.uuid4()),
        "name": t_name,
        "description": f"تأهل تلقائي من {league.get('name', 'الدوري المكتمل')}",
        "rules": "نظام خروج مغلوب (Single Elimination) - يتأهل أفضل 4 كلانات من الدوري.",
        "format": "خروج مغلوب",
        "max_participants": 4,
        "losers_bracket": False,
        "status": "live" if len(participants) >= 2 else "registration",
        "starts_at": iso(now),
        "plus_window_until": iso(now),
        "participants": participants,
        "bracket": _build_initial_bracket(participants) if len(participants) >= 2 else [],
        "champion_clan_id": None,
        "created_by": created_by or league.get("created_by") or "system",
        "created_at": iso(now),
        "finished_at": None,
        "is_auto_generated": True,
        "source_league_id": league["id"],
        "source_league_name": league.get("name", ""),
    }
    await db.tournaments.insert_one(tournament)

    if tournament["status"] == "live":
        await _create_round_matches(tournament, 0)
        if len(tournament["bracket"]) > 1:
            for slot in tournament["bracket"][1]:
                if slot.get("clan_a_id") and slot.get("clan_b_id") and not slot.get("match_id"):
                    await _create_round_matches(tournament, 1)
                    break

    await db.leagues.update_one(
        {"id": league["id"]},
        {
            "$set": {
                "super_rivals_tournament_id": tournament["id"],
                "super_rivals_tournament_name": tournament["name"],
                "super_rivals_created_at": iso(now),
                "qualified_clan_ids": participants,
            }
        },
    )
    logger.info(
        "Auto-created super rivals tournament '%s' from league '%s' with %s participants",
        tournament["name"],
        league.get("name", league["id"]),
        len(participants),
    )
    return tournament


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
        if bool(prev.get("super_rivals_enabled", False)):
            await _create_super_rivals_tournament_from_league({**prev, **update_fields})
        # Reset all clan points/wins/losses for the new league
        await db.clans.update_many({}, {"$set": {"points": 0, "wins": 0, "losses": 0}})
        await db.users.update_many({"role": {"$ne": "owner"}}, {"$set": {"points": 0}})
    new_league = {
        "id": str(uuid.uuid4()),
        "key": key,
        "name": _current_league_name(),
        "status": "active",
        "super_rivals_enabled": False,
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


def _month_window(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


async def _award_most_active_player_for_month(year: int, month: int) -> Optional[str]:
    start, end = _month_window(year, month)
    pipeline = [
        {"$match": {"attendance_events": {"$exists": True, "$ne": []}}},
        {"$unwind": "$attendance_events"},
        {"$match": {
            "attendance_events.action": "checkin",
            "attendance_events.at": {"$gte": iso(start), "$lt": iso(end)},
        }},
        {"$group": {"_id": "$attendance_events.user_id", "checkins": {"$sum": 1}}},
        {"$sort": {"checkins": -1, "_id": 1}},
        {"$limit": 1},
    ]
    top = await db.clan_attendance.aggregate(pipeline).to_list(1)
    if not top:
        return None
    winner_id = top[0].get("_id")
    if not winner_id:
        return None
    winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "id": 1, "username": 1})
    if not winner:
        return None

    await _extend_person_plus_for_user(winner_id, months=1)
    await _create_news_post(
        kind="hall_of_fame_attendance",
        title="أكثر لاعب تحضيراً",
        body=f"👑 **تكريم منارة الانضباط!** نهنئ اللاعب **{winner['username']}** لحصوله على لقب 'أكثر لاعب تحضيراً' هذا الشهر! تم مكافأته باشتراك Person Plus مجاني. حافظوا على حضوركم!",
        payload={"user_id": winner_id, "year": year, "month": month, "metric": "attendance_checkins"},
    )
    return winner_id


async def _award_player_of_month_for_month(year: int, month: int) -> Optional[str]:
    start, end = _month_window(year, month)
    pipeline = [
        {"$match": {"mvp_votes": {"$exists": True, "$ne": []}}},
        {"$unwind": "$mvp_votes"},
        {"$match": {"mvp_votes.created_at": {"$gte": iso(start), "$lt": iso(end)}}},
        {"$group": {"_id": "$mvp_votes.candidate_id", "votes": {"$sum": 1}}},
        {"$sort": {"votes": -1, "_id": 1}},
        {"$limit": 1},
    ]
    top = await db.matches.aggregate(pipeline).to_list(1)
    if not top:
        return None
    winner_id = top[0].get("_id")
    if not winner_id:
        return None
    winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "id": 1, "username": 1})
    if not winner:
        return None

    await _extend_person_plus_for_user(winner_id, months=1)
    await _create_news_post(
        kind="hall_of_fame_pom",
        title="نجم الدوري للشهر",
        body=f"⚽ **نجم الشهر الساطع!** تصفيق حار للبطل **{winner['username']}** الذي حصد أعلى نسبة تصويت كـ 'نجم المباراة' وتوّج بلقب 'نجم الدوري لهذا الشهر'! استمتع بميزات الـ Person Plus الخاصة بك مجاناً!",
        payload={"user_id": winner_id, "year": year, "month": month, "metric": "pom_votes"},
    )
    return winner_id


async def _run_monthly_hall_of_fame_if_due(now: Optional[datetime] = None) -> bool:
    now = now or now_utc()
    # Run exactly in the last-day 23:59 window; loop ticks every minute.
    tomorrow = now + timedelta(days=1)
    is_last_day = tomorrow.month != now.month
    if not (is_last_day and now.hour == 23 and now.minute == 59):
        return False

    period = f"{now.year:04d}-{now.month:02d}"
    lock = await db.system_jobs.find_one_and_update(
        {"job": "monthly_hall_of_fame", "period": period},
        {"$setOnInsert": {"id": str(uuid.uuid4()), "job": "monthly_hall_of_fame", "period": period, "created_at": iso(now)}},
        upsert=True,
        return_document=ReturnDocument.BEFORE,
    )
    if lock:
        return False

    attendance_winner = await _award_most_active_player_for_month(now.year, now.month)
    pom_winner = await _award_player_of_month_for_month(now.year, now.month)
    await db.system_jobs.update_one(
        {"job": "monthly_hall_of_fame", "period": period},
        {"$set": {
            "ran_at": iso(now_utc()),
            "attendance_winner_id": attendance_winner,
            "pom_winner_id": pom_winner,
        }},
    )
    return True


async def _monthly_hall_of_fame_loop() -> None:
    while True:
        try:
            await _run_monthly_hall_of_fame_if_due()
        except Exception as exc:  # noqa: BLE001
            logger.error("Monthly hall of fame loop error: %s", exc)
        await asyncio.sleep(60)


# ---------------- CUSTOM LEAGUES (multi-league system) ----------------
def _validate_rules_image(img: str, label: str = "صورة القوانين") -> str:
    img = (img or "").strip()
    if not img:
        return ""
    if img.startswith("data:image/"):
        if len(img) > 4_500_000:  # ~3MB binary
            raise HTTPException(400, f"{label} كبيرة جداً (الحد 3MB)")
    elif not img.startswith("http"):
        raise HTTPException(400, f"{label} يجب أن تكون رابطاً أو ملف صورة")
    return img


def _parse_legacy_league_rules(raw: str) -> List[str]:
    if not raw:
        return []
    parts = []
    for p in raw.replace("؛", ";").replace("|", "\n").split("\n"):
        for chunk in p.split(";"):
            s = chunk.strip()
            if s:
                parts.append(s)
    return parts


def _normalized_league_rules(league: dict) -> List[dict]:
    parsed = _parse_legacy_league_rules((league.get("rules") or "").strip())
    if not parsed:
        return []
    league_id = (league.get("id") or "league").strip() or "league"
    base_ts = (league.get("started_at") or league.get("created_at") or "").strip() or iso(now_utc())
    unique_images = []
    if league.get("rules_image"):
        img = _validate_rules_image(league.get("rules_image"), "صورة القوانين")
        if img:
            unique_images = [img]
    out = []
    for i, text in enumerate(parsed, start=1):
        out.append({
            "id": f"legacy-{league_id}-{i}",
            "title": f"قاعدة {i}",
            "body": text,
            "order": i,
            "images": unique_images if i == 1 else [],
            "created_at": base_ts,
            "updated_at": base_ts,
        })
    return out


def _effective_league_rules(league: dict) -> List[dict]:
    stored = league.get("rules_items")
    if isinstance(stored, list) and stored:
        league_id = (league.get("id") or "league").strip() or "league"
        cleaned = []
        for idx, raw in enumerate(stored, start=1):
            if not isinstance(raw, dict):
                continue
            norm = _normalize_rule_doc(dict(raw))
            body = (norm.get("body") or "").strip()
            if not body:
                continue
            norm["id"] = (norm.get("id") or "").strip() or f"legacy-{league_id}-{idx}"
            norm["title"] = (norm.get("title") or "").strip() or f"قاعدة {idx}"
            norm["order"] = int(norm.get("order") or idx)
            norm["created_at"] = norm.get("created_at") or iso(now_utc())
            norm["updated_at"] = norm.get("updated_at") or iso(now_utc())
            cleaned.append(norm)
        cleaned.sort(key=lambda r: int(r.get("order") or 0))
        return cleaned
    return _normalized_league_rules(league)


async def _parse_rule_payload_from_request(request: Request) -> RuleIn:
    ctype = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" not in ctype:
        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(400, "صيغة الطلب غير صحيحة")
        return RuleIn.model_validate(raw or {})

    form = await request.form()

    def _form_text(name: str, default: str = "") -> str:
        val = form.get(name, default)
        if val is None:
            return default
        return str(val)

    raw_images = []

    # Accept repeated text fields: images=...&images=...
    for v in form.getlist("images"):
        if isinstance(v, str) and v.strip():
            raw_images.append(v.strip())

    # Accept JSON array string in images_json
    images_json = _form_text("images_json", "").strip()
    if images_json:
        try:
            parsed = json.loads(images_json)
            if isinstance(parsed, list):
                raw_images.extend([str(x).strip() for x in parsed if str(x).strip()])
        except Exception:
            raise HTTPException(400, "صيغة images_json غير صحيحة")

    def _file_to_data_url(upload: UploadFile) -> Optional[str]:
        mime = (upload.content_type or "").strip().lower()
        if not mime.startswith("image/"):
            raise HTTPException(400, "يُسمح فقط برفع ملفات صور")
        return mime

    # Accept files from image_file / images_files / images
    files = []
    for key in ("image_file", "images_files", "images"):
        for f in form.getlist(key):
            if getattr(f, "filename", None) and hasattr(f, "read"):
                files.append(f)

    for f in files:
        mime = _file_to_data_url(f)
        content = await f.read()
        if len(content) > 3_000_000:
            raise HTTPException(400, f"الصورة {f.filename or ''} كبيرة جداً (الحد 3MB)")
        raw_images.append(f"data:{mime};base64,{base64.b64encode(content).decode()}")

    payload = {
        "title": _form_text("title", ""),
        "body": _form_text("body", ""),
        "order": int(_form_text("order", "0") or 0),
        "image": _form_text("image", ""),
        "images": raw_images,
    }
    return RuleIn.model_validate(payload)


@api.post("/leagues/custom")
async def create_custom_league(body: CustomLeagueIn, user: dict = Depends(get_current_user)):
    """Owner/Admin creates a custom league with its own name, game, rules and rule image.
    Multiple custom leagues can run simultaneously."""
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    rules_image = _validate_rules_image(body.rules_image or "")
    doc = {
        "id": str(uuid.uuid4()),
        "key": f"custom-{uuid.uuid4().hex[:8]}",
        "name": body.name,
        "game": body.game,
        "rules": body.rules or "",
        "rules_image": rules_image,
        "super_rivals_enabled": bool(body.super_rivals_enabled),
        "description": body.description or "",
        "is_custom": True,
        "status": "active",
        "started_at": iso(now_utc()),
        "finished_at": None,
        "champion_clan_id": None,
        "champion_clan_name": None,
        "created_by": user["id"],
    }
    await db.leagues.insert_one(doc)
    doc.pop("_id", None)
    asyncio.create_task(_send_discord_embed(
        title=f"🏆 دوري جديد مفتوح: {body.name}",
        description=f"اللعبة: {body.game}\n{body.description or ''}",
        color=0xFFCC00,
    ))
    return doc


@api.put("/leagues/{league_id}")
async def update_custom_league(league_id: str, body: CustomLeagueUpdateIn, user: dict = Depends(get_current_user)):
    """Owner/Admin edits a custom league (name, game, rules, image, optional status)."""
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    existing = await db.leagues.find_one({"id": league_id})
    if not existing:
        raise HTTPException(404, "الدوري غير موجود")

    update_fields = {}
    if body.name is not None:
        update_fields["name"] = body.name
    if body.game is not None:
        update_fields["game"] = body.game
    if body.rules is not None:
        update_fields["rules"] = body.rules or ""
    if body.description is not None:
        update_fields["description"] = body.description or ""
    if body.rules_image is not None:
        update_fields["rules_image"] = _validate_rules_image(body.rules_image or "")
    if body.super_rivals_enabled is not None:
        update_fields["super_rivals_enabled"] = bool(body.super_rivals_enabled)

    if update_fields:
        await db.leagues.update_one({"id": league_id}, {"$set": update_fields})

    if body.status in ("finished", "completed") and existing.get("status") == "active":
        await finish_custom_league(league_id, user)
    elif body.status == "active" and existing.get("status") != "active":
        await db.leagues.update_one(
            {"id": league_id},
            {"$set": {"status": "active", "finished_at": None}},
        )

    fresh = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    return fresh


@api.patch("/leagues/{league_id}/status")
async def update_league_status(league_id: str, body: LeagueStatusUpdateIn, user: dict = Depends(get_current_user)):
    """Explicit status trigger. Setting completed/finished runs Super Rivals automation."""
    if body.status in ("finished", "completed"):
        return await finish_custom_league(league_id, user)

    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    league = await db.leagues.find_one({"id": league_id})
    if not league:
        raise HTTPException(404, "الدوري غير موجود")

    await db.leagues.update_one(
        {"id": league_id},
        {"$set": {"status": "active", "finished_at": None}},
    )
    fresh = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    return {"ok": True, "league": fresh}


@api.get("/leagues/active")
async def list_active_leagues():
    docs = await db.leagues.find({"status": "active"}, {"_id": 0}).sort("started_at", -1).to_list(50)
    return docs


@api.post("/leagues/{league_id}/join")
async def join_league(league_id: str, user: dict = Depends(get_current_user)):
    """Clan leader (or staff) registers their clan into a custom league."""
    league = await db.leagues.find_one({"id": league_id})
    if not league:
        raise HTTPException(404, "الدوري غير موجود")
    if not user.get("clan_id"):
        raise HTTPException(400, "يجب أن تكون في كلان")
    clan = await _get_clan(user["clan_id"])
    if not _is_clan_staff(clan, user) and not is_staff(user):
        raise HTTPException(403, "فقط القائد أو نائبه")
    await _assert_min_members_for_competitions(clan)
    _assert_clan_can_match(clan)
    await db.clans.update_one({"id": clan["id"]}, {"$addToSet": {"league_ids": league_id}})
    return {"ok": True}


@api.get("/leagues/{league_id}")
async def get_league_detail(league_id: str):
    """Return a single league details object."""
    league = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not league:
        raise HTTPException(404, "الدوري غير موجود")
    return league


@api.get("/leagues/{league_id}/rules")
async def list_league_rules(league_id: str):
    league = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not league:
        raise HTTPException(404, "الدوري غير موجود")
    return _effective_league_rules(league)


@api.post("/leagues/{league_id}/rules")
async def create_league_rule(league_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    league = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not league:
        raise HTTPException(404, "الدوري غير موجود")

    body = await _parse_rule_payload_from_request(request)
    rules = _effective_league_rules(league)
    payload = _normalize_rule_doc(body.model_dump())
    new_rule = {
        "id": str(uuid.uuid4()),
        **payload,
        "order": int(payload.get("order") or (len(rules) + 1)),
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    }
    rules.append(new_rule)
    rules.sort(key=lambda r: int(r.get("order") or 0))
    await db.leagues.update_one({"id": league_id}, {"$set": {"rules_items": rules}})
    return new_rule


@api.put("/leagues/{league_id}/rules/{rule_id}")
async def update_league_rule(league_id: str, rule_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    league = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not league:
        raise HTTPException(404, "الدوري غير موجود")

    rules = _effective_league_rules(league)
    target = next((r for r in rules if r.get("id") == rule_id), None)
    if not target:
        raise HTTPException(404, "القاعدة غير موجودة")

    body = await _parse_rule_payload_from_request(request)
    payload = _normalize_rule_doc(body.model_dump())
    target.update({
        **payload,
        "order": int(payload.get("order") or target.get("order") or 1),
        "updated_at": iso(now_utc()),
    })
    rules.sort(key=lambda r: int(r.get("order") or 0))
    await db.leagues.update_one({"id": league_id}, {"$set": {"rules_items": rules}})
    return target


@api.delete("/leagues/{league_id}/rules/{rule_id}")
async def delete_league_rule(league_id: str, rule_id: str, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    league = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not league:
        raise HTTPException(404, "الدوري غير موجود")

    rules = _effective_league_rules(league)
    kept = [r for r in rules if r.get("id") != rule_id]
    if len(kept) == len(rules):
        raise HTTPException(404, "القاعدة غير موجودة")
    await db.leagues.update_one({"id": league_id}, {"$set": {"rules_items": kept}})
    return {"ok": True}


@api.get("/leagues/{league_id}/leaderboard")
async def league_leaderboard(league_id: str):
    """Per-league standings: each league tracks its own independent points/wins/losses.
    Returns clans sorted by points desc, then wins desc."""
    league = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not league:
        raise HTTPException(404, "الدوري غير موجود")
    rows = await db.league_standings.find(
        {"league_id": league_id}, {"_id": 0}
    ).sort([("points", -1), ("wins", -1)]).to_list(200)
    # Also include clans that joined but haven't played yet (0 points), for visibility
    joined_clans = await db.clans.find(
        {"league_ids": league_id, "archived": {"$ne": True}},
        {"_id": 0, "id": 1, "name": 1, "tag": 1, "is_plus": 1, "plus_until": 1},
    ).to_list(200)
    enriched = []
    seen = set()
    for r in rows:
        clan = next((c for c in joined_clans if c["id"] == r["clan_id"]), None)
        if not clan:
            clan = await db.clans.find_one(
                {"id": r["clan_id"]},
                {"_id": 0, "id": 1, "name": 1, "tag": 1, "is_plus": 1, "plus_until": 1},
            )
        if not clan:
            continue
        seen.add(clan["id"])
        enriched.append({
            "clan_id": clan["id"],
            "clan_name": clan["name"],
            "clan_tag": clan["tag"],
            "is_plus": bool(clan.get("is_plus")),
            "points": r.get("points", 0),
            "wins": r.get("wins", 0),
            "losses": r.get("losses", 0),
        })
    for c in joined_clans:
        if c["id"] in seen:
            continue
        enriched.append({
            "clan_id": c["id"],
            "clan_name": c["name"],
            "clan_tag": c["tag"],
            "is_plus": bool(c.get("is_plus")),
            "points": 0, "wins": 0, "losses": 0,
        })
    enriched.sort(key=lambda x: (-x["points"], -x["wins"]))
    return {"league": league, "standings": enriched}


@api.post("/leagues/{league_id}/finish")
async def finish_custom_league(league_id: str, user: dict = Depends(get_current_user)):
    """Owner/Admin closes a custom league and awards the badge to the top-points
    participating clan."""
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    league = await db.leagues.find_one({"id": league_id})
    if not league:
        raise HTTPException(404, "غير موجود")
    if league.get("status") != "active":
        raise HTTPException(400, "الدوري ليس نشطاً")
    top_row = await db.league_standings.find_one(
        {"league_id": league_id}, {"_id": 0},
        sort=[("points", -1), ("wins", -1)],
    )
    top = None
    if top_row:
        top = await db.clans.find_one(
            {"id": top_row["clan_id"], "archived": {"$ne": True}}, {"_id": 0}
        )
    if not top:
        # Fallback: any joined clan with the most global points
        top = await db.clans.find_one(
            {"league_ids": league_id, "archived": {"$ne": True}},
            {"_id": 0}, sort=[("points", -1)],
        )
    update = {"status": "finished", "finished_at": iso(now_utc())}
    if top:
        update["champion_clan_id"] = top["id"]
        update["champion_clan_name"] = top["name"]
        await db.clans.update_one(
            {"id": top["id"]},
            {"$push": {"trophies": {
                "id": str(uuid.uuid4()),
                "kind": "league",
                "label": f"بطل {league['name']}",
                "league_key": league.get("key"),
                "league_id": league_id,
                "awarded_at": iso(now_utc()),
            }}}
        )
    await db.leagues.update_one({"id": league_id}, {"$set": update})
    completed_league = {**league, **update}
    generated = None
    if bool(completed_league.get("super_rivals_enabled", False)):
        generated = await _create_super_rivals_tournament_from_league(completed_league, created_by=user.get("id"))
    return {
        "ok": True,
        "champion_clan_id": update.get("champion_clan_id"),
        "super_rivals_enabled": bool(completed_league.get("super_rivals_enabled", False)),
        "super_rivals_tournament_id": generated.get("id") if generated else None,
        "qualified_clan_ids": generated.get("participants", []) if generated else [],
    }


@api.post("/leagues/{league_id}/complete")
async def complete_custom_league(league_id: str, user: dict = Depends(get_current_user)):
    """Alias trigger for league completion automation (same behavior as /finish)."""
    return await finish_custom_league(league_id, user)


# ---------------- AI: welcome bot + toxicity monitor + scoreboard OCR ----------------
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "").strip()
_AI_MODEL_PROVIDER = ("openai", "gpt-5.4")  # default per integration playbook


async def _ai_chat(system_prompt: str, user_text: str, session_id: str,
                   image_b64: Optional[str] = None, max_chars: int = 4000) -> str:
    """Single-shot AI call. Returns the model's text reply or '' on failure."""
    if not EMERGENT_LLM_KEY:
        return ""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system_prompt,
        ).with_model(*_AI_MODEL_PROVIDER)
        kwargs = {"text": user_text[:max_chars]}
        if image_b64:
            raw = image_b64.split(",", 1)[1] if image_b64.startswith("data:") else image_b64
            kwargs["file_contents"] = [ImageContent(image_base64=raw)]
        resp = await chat.send_message(UserMessage(**kwargs))
        return (resp or "").strip()
    except Exception as exc:
        logger.warning(f"AI chat error: {exc}")
        return ""


async def _post_system_chat(match_id: str, text: str, image: Optional[str] = None,
                            username: str = "AI الحكم", role: str = "admin") -> None:
    await db.chat_messages.insert_one({
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "user_id": "ai-bot",
        "username": username,
        "user_role": role,
        "user_clan_id": None,
        "type": "image" if image else "text",
        "text": text,
        "image": image,
        "video": None,
        "opponent_decision": None, "admin_decision": None, "admin_note": "",
        "created_at": iso(now_utc()),
    })


async def _ai_welcome_for_match(match_id: str, clan_a: dict, clan_b: dict,
                                league_id: Optional[str] = None) -> None:
    league = None
    if league_id:
        league = await db.leagues.find_one({"id": league_id}, {"_id": 0})
    if not EMERGENT_LLM_KEY:
        base = f"🤖 مرحباً بكلان {clan_a['name']} وكلان {clan_b['name']}! ابدأوا BO3 — التزموا بقوانين الدوري."
        if league:
            base = f"🤖 أهلاً بكم في **{league['name']}**\nاللعبة: {league.get('game','Call of Duty')}\n\n{base}"
        await _post_system_chat(match_id, base)
    else:
        ctx = f"مرحب بـ {clan_a['name']} ({clan_a['tag']}) و {clan_b['name']} ({clan_b['tag']}). BO3 Call of Duty."
        if league:
            ctx += f" الدوري: {league['name']} — اللعبة: {league.get('game','Call of Duty')}."
        txt = await _ai_chat(
            system_prompt=(
                "أنت 'AI الحكم' في منصة Rivals لمباريات Call of Duty. "
                "اكتب رسالة ترحيب قصيرة (سطرين كحد أقصى) باللغة العربية لكلانين متباريَين، "
                "ذكّرهم بالاحترام، وحظ موفق. لا تستخدم رموز Markdown."
            ),
            user_text=ctx,
            session_id=f"welcome-{match_id}",
        )
        if not txt:
            txt = f"🤖 مرحباً {clan_a['name']} و{clan_b['name']}. حظ موفق في BO3 — التزموا الاحترام والقوانين."
        if league:
            txt = f"🏆 {league['name']}\n{txt}"
        await _post_system_chat(match_id, txt)
    # If the league has text rules, post them as a separate chat message
    if league and (league.get("rules") or "").strip():
        rules_msg = f"📜 قوانين {league['name']}:\n{league['rules']}"
        await _post_system_chat(match_id, rules_msg)
    # If the league has a rules image, post it as an image message
    if league and (league.get("rules_image") or "").strip():
        await _post_system_chat(
            match_id,
            f"🖼️ إعدادات المباراة في {league['name']}",
            image=league["rules_image"],
        )


async def _ai_toxicity_check(match_id: str, msg_id: str, user_id: str, username: str, text: str) -> None:
    """Background task — analyses message, logs warning + posts AI warning if toxic."""
    if not text.strip() or not EMERGENT_LLM_KEY:
        return
    raw = await _ai_chat(
        system_prompt=(
            "You are a strict bilingual (Arabic+English) chat moderator for an esports platform. "
            "Decide if the user's message is TOXIC: insults, slurs, harassment, threats, hate speech. "
            "Reply with ONLY a compact JSON object on one line: "
            '{"is_toxic": true|false, "severity": "low"|"medium"|"high", "reason": "short reason in Arabic"}. '
            "No prose, no markdown."
        ),
        user_text=text,
        session_id=f"tox-{match_id}-{msg_id}",
        max_chars=600,
    )
    if not raw:
        return
    import json
    try:
        snippet = raw.strip()
        if snippet.startswith("```"):
            snippet = snippet.strip("`").split("\n", 1)[-1]
        if snippet.endswith("```"):
            snippet = snippet.rsplit("```", 1)[0]
        # Extract first {...}
        i = snippet.find("{")
        j = snippet.rfind("}")
        if i >= 0 and j >= 0:
            snippet = snippet[i:j+1]
        data = json.loads(snippet)
    except Exception:
        return
    if not data.get("is_toxic"):
        return
    log = {
        "id": str(uuid.uuid4()),
        "match_id": match_id,
        "message_id": msg_id,
        "user_id": user_id,
        "username": username,
        "original_text": text,
        "severity": data.get("severity", "low"),
        "reason": data.get("reason", "")[:240],
        "created_at": iso(now_utc()),
    }
    await db.toxicity_log.insert_one(log)
    warn = f"⚠️ تحذير من AI الحكم: @{username} — {log['reason']}. خفّف الحدّة من فضلك."
    await _post_system_chat(match_id, warn)


@api.get("/admin/toxicity-log")
async def admin_toxicity_log(user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للمنظمين فقط")
    docs = await db.toxicity_log.find({}, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    return docs


# ---------------- DISCORD BRIDGE (job-based, rate-limit friendly) ----------------
_DISCORD_BRIDGE_SECRET = (os.environ.get("DISCORD_BRIDGE_SECRET") or "").strip()


def _require_discord_bridge_secret(request: Request) -> None:
    """Optional machine-to-machine auth for bot-only endpoints."""
    if not _DISCORD_BRIDGE_SECRET:
        return
    provided = (request.headers.get("x-discord-bridge-secret") or "").strip()
    if provided != _DISCORD_BRIDGE_SECRET:
        raise HTTPException(403, "discord bridge secret invalid")


def _normalize_discord_snowflake(value: str, field_name: str) -> str:
    v = (value or "").strip()
    if not v.isdigit():
        raise HTTPException(400, f"{field_name} غير صالح")
    return v


def _sanitize_ticket_category(doc: dict) -> dict:
    return {
        "id": doc.get("id"),
        "name": doc.get("name", ""),
        "description": doc.get("description", ""),
        "emoji": doc.get("emoji", ""),
        "discord_category_id": str(doc.get("discord_category_id", "")),
        "support_role_id": str(doc.get("support_role_id", "")),
        "is_active": bool(doc.get("is_active", True)),
        "sort_order": int(doc.get("sort_order", 100)),
        "guild_id": int(doc.get("guild_id") or 0),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("updated_at", ""),
    }


async def _enqueue_discord_job(job_type: str, payload: dict, dedupe_key: Optional[str] = None, priority: int = 100) -> dict:
    now = iso(now_utc())
    if dedupe_key:
        existing = await db.discord_jobs.find_one(
            {"status": {"$in": ["queued", "processing"]}, "dedupe_key": dedupe_key},
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        if existing:
            return {"job": existing, "deduped": True}

    job = {
        "id": str(uuid.uuid4()),
        "type": job_type,
        "payload": payload,
        "dedupe_key": dedupe_key or "",
        "priority": int(priority),
        "status": "queued",
        "attempts": 0,
        "last_error": "",
        "created_at": now,
        "updated_at": now,
        "next_retry_at": now,
    }
    await db.discord_jobs.insert_one(job)
    return {"job": job, "deduped": False}


async def _discord_enqueue_clan_role_create(clan: dict) -> dict:
    try:
        return await _enqueue_discord_job(
            "clan_role_create",
            {"clan_id": clan["id"], "clan_name": clan.get("name", ""), "clan_tag": clan.get("tag", "")},
            dedupe_key=f"clan_role_create:{clan['id']}",
            priority=20,
        )
    except Exception as exc:
        logger.warning("Discord enqueue failed (clan_role_create:%s): %s", clan.get("id"), exc)
        return {"job": None, "deduped": False, "error": str(exc)}


async def _discord_enqueue_clan_role_sync_member(user_id: str, old_clan_id: str, new_clan_id: str) -> dict:
    old_cid = (old_clan_id or "").strip()
    new_cid = (new_clan_id or "").strip()
    try:
        return await _enqueue_discord_job(
            "clan_role_sync_member",
            {
                "user_id": user_id,
                "old_clan_id": old_cid,
                "new_clan_id": new_cid,
            },
            dedupe_key=f"clan_role_sync_member:{user_id}:{old_cid}:{new_cid}",
            priority=30,
        )
    except Exception as exc:
        logger.warning(
            "Discord enqueue failed (clan_role_sync_member:%s:%s->%s): %s",
            user_id,
            old_cid,
            new_cid,
            exc,
        )
        return {"job": None, "deduped": False, "error": str(exc)}


async def _discord_enqueue_plus_channels_create(clan: dict) -> dict:
    try:
        return await _enqueue_discord_job(
            "plus_channels_create",
            {"clan_id": clan["id"], "clan_name": clan.get("name", ""), "clan_tag": clan.get("tag", "")},
            dedupe_key=f"plus_channels_create:{clan['id']}",
            priority=25,
        )
    except Exception as exc:
        logger.warning("Discord enqueue failed (plus_channels_create:%s): %s", clan.get("id"), exc)
        return {"job": None, "deduped": False, "error": str(exc)}


async def _discord_enqueue_moderation_sync(
    user_id: str,
    action: str,
    reason: str = "",
    until: str = "",
    warning_points: int = 0,
) -> dict:
    until_iso = (until or "").strip()
    try:
        return await _enqueue_discord_job(
            "moderation_sync",
            {
                "user_id": user_id,
                "action": action,
                "reason": (reason or "")[:240],
                "until": until_iso,
                "warning_points": int(warning_points or 0),
            },
            dedupe_key=f"moderation_sync:{user_id}:{action}:{until_iso}:{int(warning_points or 0)}",
            priority=10,
        )
    except Exception as exc:
        logger.warning("Discord enqueue failed (moderation_sync:%s:%s): %s", user_id, action, exc)
        return {"job": None, "deduped": False, "error": str(exc)}


@api.put("/discord/link-account")
async def discord_link_account(body: DiscordLinkIn, user: dict = Depends(get_current_user)):
    did = (body.discord_id or "").strip()
    if not did.isdigit():
        raise HTTPException(400, "Discord ID غير صالح")

    conflict = await db.users.find_one({"discord_id": did, "id": {"$ne": user["id"]}}, {"_id": 0, "id": 1})
    if conflict:
        raise HTTPException(400, "هذا Discord ID مرتبط بحساب آخر")

    await db.users.update_one({"id": user["id"]}, {"$set": {"discord_id": did, "discord_linked_at": iso(now_utc())}})
    return {"ok": True, "discord_id": did}



@api.get("/discord/ticket-categories")
async def discord_ticket_categories_list(user: dict = Depends(get_current_user), include_inactive: bool = False):
    if not is_staff(user):
        raise HTTPException(403, "للإدارة فقط")
    query = {}
    if not include_inactive:
        query["is_active"] = True
    docs = await db.discord_ticket_categories.find(query, {"_id": 0}).sort([("sort_order", 1), ("name", 1)]).to_list(200)
    return [_sanitize_ticket_category(d) for d in docs]


@api.post("/discord/ticket-categories")
async def discord_ticket_category_create(body: DiscordTicketCategoryUpsertIn, user: dict = Depends(get_current_user)):
    if not is_owner(user):
        raise HTTPException(403, "للأونر فقط")

    guild_id = int((os.environ.get("DISCORD_GUILD_ID") or "0").strip() or 0)
    if guild_id <= 0:
        raise HTTPException(400, "DISCORD_GUILD_ID غير مضبوط")

    category_id = _normalize_discord_snowflake(body.discord_category_id, "discord_category_id")
    support_role_id = _normalize_discord_snowflake(body.support_role_id, "support_role_id")

    doc = {
        "id": str(uuid.uuid4()),
        "guild_id": int(guild_id),
        "name": body.name.strip(),
        "description": (body.description or "").strip(),
        "emoji": (body.emoji or "").strip(),
        "discord_category_id": category_id,
        "support_role_id": support_role_id,
        "is_active": bool(body.is_active if body.is_active is not None else True),
        "sort_order": int(body.sort_order if body.sort_order is not None else 100),
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
        "created_by": user.get("id"),
    }
    await db.discord_ticket_categories.insert_one(doc)
    return _sanitize_ticket_category(doc)


@api.put("/discord/ticket-categories/{ticket_category_id}")
async def discord_ticket_category_update(ticket_category_id: str, body: DiscordTicketCategoryUpsertIn, user: dict = Depends(get_current_user)):
    if not is_owner(user):
        raise HTTPException(403, "للأونر فقط")

    existing = await db.discord_ticket_categories.find_one({"id": ticket_category_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "فئة التذكرة غير موجودة")

    category_id = _normalize_discord_snowflake(body.discord_category_id, "discord_category_id")
    support_role_id = _normalize_discord_snowflake(body.support_role_id, "support_role_id")

    update = {
        "name": body.name.strip(),
        "description": (body.description or "").strip(),
        "emoji": (body.emoji or "").strip(),
        "discord_category_id": category_id,
        "support_role_id": support_role_id,
        "is_active": bool(body.is_active if body.is_active is not None else True),
        "sort_order": int(body.sort_order if body.sort_order is not None else 100),
        "updated_at": iso(now_utc()),
        "updated_by": user.get("id"),
    }
    await db.discord_ticket_categories.update_one({"id": ticket_category_id}, {"$set": update})
    fresh = await db.discord_ticket_categories.find_one({"id": ticket_category_id}, {"_id": 0})
    return _sanitize_ticket_category(fresh or {"id": ticket_category_id, **update})


@api.delete("/discord/ticket-categories/{ticket_category_id}")
async def discord_ticket_category_delete(ticket_category_id: str, user: dict = Depends(get_current_user)):
    if not is_owner(user):
        raise HTTPException(403, "للأونر فقط")
    result = await db.discord_ticket_categories.delete_one({"id": ticket_category_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "فئة التذكرة غير موجودة")
    return {"ok": True, "deleted_id": ticket_category_id}

@api.post("/discord/clan-role/create")
async def discord_clan_role_create(body: DiscordClanRoleCreateIn, user: dict = Depends(get_current_user)):
    clan = await _get_clan(body.clan_id)
    if not (is_staff(user) or _is_clan_staff(clan, user)):
        raise HTTPException(403, "غير مصرح")
    r = await _discord_enqueue_clan_role_create(clan)
    return {"ok": True, "deduped": bool(r.get("deduped")), "job_id": ((r.get("job") or {}).get("id"))}


@api.post("/discord/clan-role/sync-member")
async def discord_clan_role_sync_member(body: DiscordClanRoleSyncMemberIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للإدارة فقط")
    r = await _discord_enqueue_clan_role_sync_member(
        user_id=body.user_id,
        old_clan_id=body.old_clan_id or "",
        new_clan_id=body.new_clan_id or "",
    )
    return {"ok": True, "deduped": bool(r.get("deduped")), "job_id": ((r.get("job") or {}).get("id"))}


@api.post("/discord/plus-channels/create")
async def discord_plus_channels_create(body: DiscordPlusChannelsCreateIn, user: dict = Depends(get_current_user)):
    clan = await _get_clan(body.clan_id)
    if not (is_staff(user) or _is_clan_staff(clan, user)):
        raise HTTPException(403, "غير مصرح")
    if not _clan_is_plus(clan):
        raise HTTPException(403, "الميزة متاحة لكلانات Plus فقط")

    r = await _discord_enqueue_plus_channels_create(clan)
    return {"ok": True, "deduped": bool(r.get("deduped")), "job_id": ((r.get("job") or {}).get("id"))}


@api.post("/discord/moderation/sync")
async def discord_moderation_sync(body: DiscordModerationSyncIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للإدارة فقط")
    r = await _discord_enqueue_moderation_sync(
        user_id=body.user_id,
        action=body.action,
        reason=body.reason or "",
        until=body.until or "",
        warning_points=int(body.warning_points or 0),
    )
    return {"ok": True, "deduped": bool(r.get("deduped")), "job_id": ((r.get("job") or {}).get("id"))}


@api.post("/discord/tickets/create")
async def discord_ticket_create(body: DiscordTicketCreateIn, user: dict = Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403, "للإدارة فقط")
    r = await _enqueue_discord_job(
        "ticket_create",
        {
            "user_id": body.user_id,
            "subject": (body.subject or "")[:120],
            "message": (body.message or "")[:2000],
            "requested_by": user.get("id"),
        },
        dedupe_key=f"ticket_create:{body.user_id}:{(body.subject or '').strip()}",
        priority=40,
    )
    return {"ok": True, "deduped": r["deduped"], "job_id": r["job"]["id"]}


@api.get("/discord/users/by-discord/{discord_id}")
async def discord_user_by_discord_id(discord_id: str, request: Request):
    """Bot helper endpoint for account-link lookup."""
    _require_discord_bridge_secret(request)
    d = (discord_id or "").strip()
    if not d.isdigit():
        raise HTTPException(400, "Discord ID غير صالح")
    u = await db.users.find_one({"discord_id": d}, {"_id": 0, "id": 1, "username": 1, "clan_id": 1, "role": 1})
    if not u:
        return {"found": False}
    return {"found": True, "user": u}


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "service": "rivals-api",
        "time": iso(now_utc()),
    }


@app.get("/readyz")
async def readyz():
    try:
        await db.command("ping")
        return {
            "ok": True,
            "db": "up",
            "time": iso(now_utc()),
        }
    except Exception as exc:
        raise HTTPException(503, f"Database not ready: {exc}")


app.include_router(api)

# Serve uploaded videos via /api/uploads/videos/*
app.mount("/api/uploads/videos", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/api/uploads/clan_logos", StaticFiles(directory=str(CLAN_LOGO_UPLOAD_DIR)), name="clan-logos-uploads")
app.mount("/api/uploads/guard", StaticFiles(directory=str(GUARD_UPLOAD_DIR)), name="guard-uploads")
app.mount("/api/downloads", StaticFiles(directory=str(DOWNLOADS_DIR)), name="downloads")

_cors_env = os.environ.get("CORS_ORIGINS", "").strip()
if _cors_env:
    _cors_origins = [o.strip().rstrip("/") for o in _cors_env.split(",") if o.strip()]
else:
    _app_env = (os.environ.get("APP_ENV") or os.environ.get("ENV") or "development").strip().lower()
    if _app_env in ("prod", "production"):
        raise RuntimeError("CORS_ORIGINS must be set explicitly in production")
    _cors_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    logger.warning("CORS_ORIGINS not set. Using localhost origins for development only.")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
