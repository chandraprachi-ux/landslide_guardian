import base64
import hashlib
import hmac
import json
import os
import time

SECRET = os.getenv("ADMIN_SECRET", "change-this-sih-secret")


def _sign(payload: str) -> str:
    return hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_token(username: str, ttl_seconds: int = 7200) -> str:
    payload = json.dumps({"u": username, "exp": int(time.time()) + ttl_seconds}, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return encoded + "." + _sign(encoded)


def verify_token(token: str) -> bool:
    try:
        encoded, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(encoded)):
            return False
        padding = "=" * (-len(encoded) % 4)
        data = json.loads(base64.urlsafe_b64decode((encoded + padding).encode()))
        return bool(data.get("u")) and int(data.get("exp", 0)) > int(time.time())
    except Exception:
        return False
