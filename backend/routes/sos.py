from fastapi import APIRouter, HTTPException, Header
from ..database.mongodb import db_manager, clean_document
from ..models.schemas import CitizenRegisterRequest, SOSBroadcastRequest
from ..services.monitor import find_verified_recipients
from ..services.notification_service import dispatch_email_sos

router = APIRouter()


@router.post("/sos/register")
async def register_citizen(citizen: CitizenRegisterRequest):
    try:
        doc = citizen.model_dump()
        doc["email_verified"] = False
        doc["account_status"] = "PENDING_VERIFICATION"
        db_manager.citizens.update_one(
            {"email": citizen.email.lower(), "location": citizen.location},
            {"$set": {**doc, "email": citizen.email.lower()}},
            upsert=True,
        )
        return {
            "status": "SUCCESS",
            "message": f"Registered {citizen.name} for {citizen.location} email alerts. Email verification required before receiving SOS.",
            "email_verified": False,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not save registration.") from exc


def _admin_required(authorization: str | None):
    from ..services.admin_auth import verify_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin authentication required.")
    if not verify_token(authorization[7:]):
        raise HTTPException(status_code=401, detail="Invalid or expired admin session.")


@router.get("/sos/registrations")
async def registrations(authorization: str | None = Header(default=None)):
    _admin_required(authorization)
    docs = list(db_manager.citizens.find({}, {"_id": 0}))
    return {"count": len(docs), "registrations": [clean_document(d) for d in docs]}


@router.post("/sos/dispatch")
async def dispatch_sos_alert(req: SOSBroadcastRequest, authorization: str | None = Header(default=None)):
    _admin_required(authorization)
    # Admin-only MANUAL dispatch — sends only to VERIFIED registered residents
    # whose city/area or region matches the alert location.
    matching = find_verified_recipients(req.location, "")
    # Count unverified residents matching by location so admin sees the gap.
    lk = req.location.strip().lower()
    unverified = sum(
        1 for u in db_manager.citizens.find()
        if u.get("email_verified") is not True and lk in (u.get("location") or u.get("region") or "").lower()
    )
    result = dispatch_email_sos(req.location, matching, req.custom_message)
    result["unverified_excluded"] = unverified
    if not matching:
        result["status"] = "NO_VERIFIED_RECIPIENTS"
        result["note"] = "No EMAIL-VERIFIED residents registered for this region yet. Register and verify residents to enable SOS."
    return result
