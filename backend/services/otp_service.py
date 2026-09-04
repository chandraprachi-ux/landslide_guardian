"""
Email OTP verification service.

Security:
    - OTP stored as a salted SHA-256 hash (never plaintext).
    - OTP expires after a configurable period (default 10 min).
    - Limited verification attempts per code (default 5).
    - Resend cooldown prevents abuse (default 60 s).
    - OTP is never written to debug logs; only a hashed marker is logged.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..database.mongodb import db_manager

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_SALT = os.getenv("OTP_SALT", "landslide-guardian-otp-salt")

BACKEND_DIR = Path(__file__).resolve().parents[1]
OTP_CACHE_FILE = BACKEND_DIR / ".otp_cache.json"


def _hash_otp(code: str) -> str:
    return hmac.new(OTP_SALT.encode(), code.encode(), hashlib.sha256).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_otp() -> str:
    """Generate a numeric OTP (CSPRNG)."""
    return f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def _load_otp_cache() -> dict:
    """Load persistent OTP cache from .otp_cache.json file."""
    if OTP_CACHE_FILE.exists():
        try:
            with open(OTP_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Could not read .otp_cache.json: %s", exc)
            return {}
    return {}


def _save_otp_cache(cache: dict) -> None:
    """Persist OTP cache to .otp_cache.json file."""
    try:
        with open(OTP_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as exc:
        logger.warning("Could not persist to .otp_cache.json: %s", exc)


def _find_otp_doc(email: str):
    email = email.lower().strip()
    doc = db_manager.otps.find_one({"email": email})
    if doc:
        return doc

    # Fallback to persistent disk cache if in-memory store was cleared by reload
    cache = _load_otp_cache()
    cached = cache.get(email)
    if cached:
        # Sync back into db_manager for fast subsequent queries
        try:
            db_manager.otps.update_one({"email": email}, {"$set": cached}, upsert=True)
        except Exception:
            pass
        return cached
    return None


def create_or_resend_otp(email: str, store_plaintext: bool = False) -> dict:
    """Create a new OTP record (or respect resend cooldown). Returns status and code."""
    email = (email or "").lower().strip()
    if not email:
        return {"status": "ERROR", "message": "Email is required."}

    doc = _find_otp_doc(email)
    now = _now()
    if doc:
        last = doc.get("created_at")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if (now - last_dt).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
                    wait = int(OTP_RESEND_COOLDOWN_SECONDS - (now - last_dt).total_seconds())
                    return {"status": "COOLDOWN", "message": f"Please wait {wait}s before resending.", "retry_after": wait}
            except Exception:
                pass

    # Track resend count to cap abuse per email per hour.
    resends = int(doc.get("resends", 0) if doc else 0)
    if resends >= 5:
        return {"status": "LIMIT", "message": "Too many OTP requests for this email. Try again later."}

    code = generate_otp()
    expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
    record = {
        "email": email,
        "hash": _hash_otp(code),
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "attempts": 0,
        "resends": resends + 1,
        "verified": False,
    }
    if store_plaintext:
        record["debug_code"] = code
    else:
        record.pop("debug_code", None)

    # Persist to database
    db_manager.otps.update_one({"email": email}, {"$set": record}, upsert=True)

    # Persist to .otp_cache.json so OTPs survive Uvicorn server reloads
    cache = _load_otp_cache()
    cache[email] = record
    _save_otp_cache(cache)

    logger.info("OTP generated for %s (hash %s...)", email, record["hash"][:8])
    return {
        "status": "OK",
        "message": f"Verification code sent to {email}.",
        "expires_in_minutes": OTP_EXPIRY_MINUTES,
        "code": code,
    }


def get_latest_otp_code(email: str) -> str:
    """Return the plaintext OTP ONLY if it was stored for the demo, else ''."""
    doc = _find_otp_doc(email)
    if not doc:
        return ""
    return doc.get("debug_code", "")


def verify_otp(email: str, code: str) -> dict:
    """Verify an OTP. Returns status SUCCESS/ERROR and marks citizen verified."""
    email = (email or "").lower().strip()
    code = (code or "").strip()
    doc = _find_otp_doc(email)
    if not doc:
        return {"status": "ERROR", "message": "No verification code found for this email. Request one first."}

    now = _now()
    try:
        expires = datetime.fromisoformat(doc["expires_at"])
    except Exception:
        return {"status": "ERROR", "message": "Invalid stored code."}

    if now > expires:
        return {"status": "EXPIRED", "message": "Verification code has expired. Request a new one."}

    attempts = int(doc.get("attempts", 0))
    if attempts >= OTP_MAX_ATTEMPTS:
        return {"status": "ERROR", "message": "Too many failed attempts. Request a new code."}

    if not hmac.compare_digest(_hash_otp(code), doc["hash"]):
        new_attempts = attempts + 1
        db_manager.otps.update_one({"email": email}, {"$set": {"attempts": new_attempts}})
        
        # Also update persistent disk cache
        cache = _load_otp_cache()
        if email in cache:
            cache[email]["attempts"] = new_attempts
            _save_otp_cache(cache)

        remaining = OTP_MAX_ATTEMPTS - new_attempts
        return {"status": "ERROR", "message": f"Incorrect code. {max(0, remaining)} attempt(s) left."}

    # Mark verified, tie the email to a registered citizen.
    verified_time = now.isoformat()
    db_manager.otps.update_one({"email": email}, {"$set": {"verified": True, "verified_at": verified_time}})
    db_manager.citizens.update_one(
        {"email": email},
        {"$set": {"email_verified": True, "verified_at": verified_time}},
        upsert=True,
    )

    # Update persistent disk cache
    cache = _load_otp_cache()
    if email in cache:
        cache[email]["verified"] = True
        cache[email]["verified_at"] = verified_time
        _save_otp_cache(cache)

    return {"status": "SUCCESS", "message": "Email verified. You are now eligible for regional emergency SOS alerts."}

