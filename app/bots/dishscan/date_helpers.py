import hashlib
from datetime import datetime, timezone, timedelta

from app.configs.logger import logger

DEFAULT_USER_TIMEZONE = "-08:00"
HISTORY_LIMIT = 20

SUPPORTED_HISTORY_DATE_FORMATS = [
    "%d.%m.%Y",
]

CACHE_TTL_DAYS = 30


def ttl_epoch(days: int = CACHE_TTL_DAYS) -> int:
    return int((now_utc() + timedelta(days=days)).timestamp())


def parse_utc_offset_to_tzinfo(offset_str: str) -> timezone:
    if not offset_str:
        return timezone(timedelta(hours=-8))

    sign = 1
    raw = offset_str.strip()

    if raw.startswith("-"):
        sign = -1
        raw = raw[1:]
    elif raw.startswith("+"):
        raw = raw[1:]

    if ":" in raw:
        hours_str, minutes_str = raw.split(":", 1)
        hours = int(hours_str)
        minutes = int(minutes_str)
    else:
        hours = int(raw)
        minutes = 0

    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(sign * delta)


def to_local_date(utc_dt: datetime, tz_name: str) -> str:
    tzinfo = parse_utc_offset_to_tzinfo(tz_name)
    return utc_dt.astimezone(tzinfo).date().isoformat()

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_utc_offset(raw: str) -> str | None:
    if not raw:
        return None

    value = raw.strip().replace("utc", "").replace("UTC", "").strip()

    try:
        if value[0] not in {"+", "-"}:
            return None

        sign = value[0]
        body = value[1:]

        if ":" in body:
            hours_str, minutes_str = body.split(":", 1)
            hours = int(hours_str)
            minutes = int(minutes_str)
        else:
            hours_float = float(body)
            hours = int(hours_float)
            minutes = int(round((hours_float - hours) * 60))

        if minutes < 0:
            minutes = abs(minutes)

        total_minutes = hours * 60 + minutes
        if total_minutes > 14 * 60:
            return None

        return f"{sign}{hours:02d}:{minutes:02d}"
    except Exception:
        return None


def today_local_date(tz_name: str = DEFAULT_USER_TIMEZONE) -> str:
    tzinfo = parse_utc_offset_to_tzinfo(tz_name)
    return datetime.now(timezone.utc).astimezone(tzinfo).date().isoformat()


def history_date_hint() -> str:
    return "dd.mm.YYYY"


def parse_flexible_date(raw: str, formats: list[str]) -> str | None:
    raw = raw.strip()
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_history_date_arg(args: list[str]) -> str | None:
    if not args:
        return None
    return parse_flexible_date(args[0], SUPPORTED_HISTORY_DATE_FORMATS)


def format_consumed_time_for_user(consumed_at: str, tz_name: str = DEFAULT_USER_TIMEZONE) -> str:
    if not consumed_at:
        return "--:--"

    try:
        dt_utc = datetime.fromisoformat(consumed_at)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)

        tzinfo = parse_utc_offset_to_tzinfo(tz_name)
        dt_local = dt_utc.astimezone(tzinfo)
        return dt_local.strftime("%H:%M")
    except Exception as e:
        logger.exception(e)
        return "--:--"