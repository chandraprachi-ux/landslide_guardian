from fastapi import APIRouter, HTTPException

from ..database.mongodb import db_manager
from ..models.schemas import SendOtpRequest, UserRegisterRequest, VerifyOtpRequest
from ..services import otp_service
from ..services.notification_service import _smtp_configured, send_otp_email
from ..services.region_config import REGION_LABELS, get_region_config

router = APIRouter()


@router.post("/auth/register")
async def register_user(req: UserRegisterRequest):
    """Register a person (name, email, region). Email starts UNVERIFIED."""
    email = req.email.lower().strip()
    region = (req.region or "").strip().lower()

    # Normalise region label so it matches the monitoring/auto-dispatch keys.
    label = None
    for rid, lab in REGION_LABELS.items():
        if rid.replace("_", " ") == region or region in (rid, lab.lower()):
            label = lab
            break
    if label is None:
        raise HTTPException(status_code=400, detail="Unknown region. Use Sikkim, Assam, Meghalaya, Mizoram, Nagaland, Arunachal Pradesh, Manipur or Tripura.")

    cfg = get_region_config(region)
    try:
        db_manager.citizens.update_one(
            {"email": email},
            {"$set": {
                "name": req.name.strip(),
                "email": email,
                "region": label.lower(),
                "location": label,          # location field is what SOS matching uses
                "email_verified": False,
                "account_status": "PENDING_VERIFICATION",
                "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not save registration.") from exc

    return {
        "status": "SUCCESS",
        "message": f"Registered {req.name.strip()} for {label}. Email verification required before receiving SOS alerts.",
        "email_verified": False,
        "verify_link_hint": "Use /auth/send-otp then /auth/verify-otp.",
    }


@router.post("/auth/send-otp")
async def send_otp(req: SendOtpRequest):
    """Send a verification OTP to the registered email."""
    email = req.email.lower().strip()
    if not db_manager.citizens.find_one({"email": email}):
        raise HTTPException(status_code=404, detail="No registration found for this email. Register first.")

    smtp_configured = _smtp_configured()
    result = otp_service.create_or_resend_otp(email, store_plaintext=not smtp_configured)
    if result["status"] in ("COOLDOWN", "LIMIT", "ERROR"):
        raise HTTPException(status_code=429 if result["status"] == "COOLDOWN" else 400, detail=result["message"])

    otp_code = result.get("code") or otp_service.get_latest_otp_code(email)
    send_result = send_otp_email(email, otp_code, otp_service.OTP_EXPIRY_MINUTES) if smtp_configured else {
        "status": "NOT_CONFIGURED", "recipient": email,
    }

    response = {
        "status": result["status"],
        "message": result["message"],
        "email_delivery": send_result.get("status"),
        "smtp_configured": smtp_configured,
        "expires_in_minutes": otp_service.OTP_EXPIRY_MINUTES,
    }
    # DEMO ONLY: surface the code when no real SMTP provider is configured.
    if not smtp_configured and otp_code:
        response["demo_otp"] = otp_code
        response["message"] = f"Verification code: {otp_code} (demo — no SMTP configured; emails are simulated)."
    return response


@router.post("/auth/verify-otp")
async def verify_otp(req: VerifyOtpRequest):
    result = otp_service.verify_otp(req.email.lower().strip(), req.code.strip())
    if result["status"] != "SUCCESS":
        status_code = 400
        if result["status"] == "EXPIRED":
            status_code = 410
        raise HTTPException(status_code=status_code, detail=result["message"])
    return result
