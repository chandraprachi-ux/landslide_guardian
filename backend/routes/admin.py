import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel
from bson.objectid import ObjectId

from ..database.mongodb import db_manager
from ..models.schemas import AdminLoginRequest
from ..services.admin_auth import create_token, verify_token
from ..services.notification_service import dispatch_email_sos

router = APIRouter()


class AdminSOSDispatchRequest(BaseModel):
    location: str
    message: str = "Emergency landslide warning from Landslide Guardian. Please move away from vulnerable slopes and follow official safety instructions."


def _require_admin(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer ") or not verify_token(authorization[7:]):
        raise HTTPException(status_code=401, detail="Invalid or expired admin session.")


@router.post("/admin/login")
async def admin_login(req: AdminLoginRequest):
    expected_user = os.getenv("ADMIN_USERNAME", "admin")
    expected_pass = os.getenv("ADMIN_PASSWORD", "guardian-demo")
    if req.username != expected_user or req.password != expected_pass:
        raise HTTPException(status_code=401, detail="Invalid administrator credentials.")
    return {"status": "SUCCESS", "token": create_token(req.username), "expires_in": 7200}


@router.get("/admin/session")
async def admin_session(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return {"authenticated": True}


@router.get("/admin/registered-users")
@router.get("/admin/registered-users/")
async def registered_users(authorization: str | None = Header(default=None),
                           verified_only: bool = Query(default=False)):
    _require_admin(authorization)
    query = {"email_verified": True} if verified_only else {}
    records = list(db_manager.citizens.find(query))
    users = []
    for r in records:
        users.append({
            "id": str(r.get("_id")),
            "name": r.get("name"),
            "email": r.get("email"),
            "region": r.get("region"),
            "location": r.get("location"),
            "email_verified": bool(r.get("email_verified", False)),
            "verified_at": r.get("verified_at"),
            "account_status": r.get("account_status"),
            "created_at": r.get("created_at"),
        })
    return {"count": len(users), "users": users}


@router.delete("/admin/registered-users")
@router.delete("/admin/registered-users/")
async def clear_all_registered_users(confirm: str = Query(default=""),
                                     authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    if confirm.lower() != "yes":
        raise HTTPException(status_code=400, detail="Must pass ?confirm=yes to clear all registered users.")

    count = db_manager.citizens.count_documents({})
    # Delete all citizens
    if hasattr(db_manager.citizens, "delete_many"):
        db_manager.citizens.delete_many({})
    elif hasattr(db_manager.citizens, "docs") and isinstance(db_manager.citizens.docs, list):
        db_manager.citizens.docs.clear()
    else:
        for d in list(db_manager.citizens.find({})):
            db_manager.citizens.delete_one({"_id": d.get("_id")})

    return {
        "status": "SUCCESS",
        "message": f"Successfully cleared {count} registered user(s).",
        "deleted_count": count
    }


@router.delete("/admin/registered-users/{user_id:path}")
async def delete_registered_user(user_id: str,
                                 confirm: str = Query(default=""),
                                 authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    if confirm.lower() != "yes":
        raise HTTPException(status_code=400, detail="Must pass ?confirm=yes to delete.")

    user_identifier = user_id.strip().strip("/")
    if not user_identifier:
        raise HTTPException(status_code=400, detail="User email or ID required.")

    query = None
    existing = None
    try:
        oid = ObjectId(user_identifier)
        query = {"_id": oid}
        existing = db_manager.citizens.find_one(query)
    except Exception:
        pass

    if not existing:
        query = {"email": user_identifier.lower()}
        existing = db_manager.citizens.find_one(query)

    if not existing:
        # Also try partial matching on email if case-folding or space difference exists
        for c in db_manager.citizens.find():
            if c.get("email", "").lower().strip() == user_identifier.lower():
                existing = c
                query = {"_id": c.get("_id")} if "_id" in c else {"email": c.get("email")}
                break

    if not existing:
        raise HTTPException(status_code=404, detail=f"User '{user_identifier}' not found.")

    db_manager.citizens.delete_one(query)
    return {
        "status": "SUCCESS",
        "message": f"Removed {existing.get('name', 'user')} ({existing.get('email')}) from registered users.",
    }


@router.post("/admin/dispatch-sos")
@router.post("/admin/dispatch-sos/")
async def admin_dispatch_sos(req: AdminSOSDispatchRequest,
                             authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    target_loc = (req.location or "").strip().lower()
    if not target_loc:
        raise HTTPException(status_code=400, detail="Location is required for emergency dispatch.")

    all_citizens = list(db_manager.citizens.find())
    matching = []

    for citizen in all_citizens:
        # STRICT VERIFICATION CHECK: Only verified residents receive SOS
        if citizen.get("email_verified") is not True:
            continue

        c_region = str(citizen.get("region") or "").strip().lower()
        c_location = str(citizen.get("location") or "").strip().lower()

        # Check exact and partial substring matches in both directions
        # e.g. "Gangtok, Sikkim" matches "Sikkim" or "Gangtok"
        if (target_loc in c_region or (c_region and c_region in target_loc) or
            target_loc in c_location or (c_location and c_location in target_loc)):
            matching.append(citizen)

    if not matching:
        unverified_count = sum(
            1 for c in all_citizens
            if c.get("email_verified") is not True and
            (target_loc in str(c.get("region") or "").lower() or target_loc in str(c.get("location") or "").lower())
        )
        msg = f"No verified residents matched '{req.location}'."
        if unverified_count > 0:
            msg += f" {unverified_count} resident(s) are registered but have not completed OTP email verification yet. Only verified residents can receive SOS alerts."
        else:
            msg += " Ensure residents have registered in this region."
        return {
            "status": "NO_VERIFIED_RECIPIENTS",
            "message": msg,
            "location": req.location,
            "recipient_count": 0,
            "unverified_pending": unverified_count,
            "logs": []
        }


    # Dispatch emergency notification via SMTP
    result = dispatch_email_sos(req.location, matching, req.message)
    return {
        "status": result.get("status", "SENT"),
        "message": f"Emergency SOS alert dispatched to {len(matching)} recipient(s) for {req.location}.",
        "location": req.location,
        "recipient_count": len(matching),
        "timestamp": result.get("timestamp"),
        "logs": result.get("logs", []),
        "smtp_configured": result.get("smtp_configured", False),
        "note": result.get("note", "")
    }


