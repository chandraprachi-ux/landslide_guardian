import html
import logging
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
from dotenv import load_dotenv

# Explicitly load backend .env variables
load_dotenv()

logger = logging.getLogger(__name__)

def _get_smtp_config():
    host = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    user = os.getenv("SMTP_USER") or os.getenv("SMTP_EMAIL", "")
    password = os.getenv("SMTP_PASSWORD", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    sender = os.getenv("ALERT_FROM_EMAIL") or user
    return host, user, password, port, sender

def _smtp_configured():
    host, user, password, _, _ = _get_smtp_config()
    return bool(host and user and password)


def _send(recipient: str, subject: str, body: str) -> dict:
    host, user, password, port, sender = _get_smtp_config()
    if not (user and password):
        print(f"[SMTP WARNING] Credentials missing. Simulated send to: {recipient}")
        return {"status": "NOT_CONFIGURED", "recipient": recipient,
                "message": "SMTP credentials not configured."}
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Landslide Guardian <{sender}>"
    msg["To"] = recipient
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo(); server.starttls(); server.ehlo()
            server.login(user, password)
            server.send_message(msg)
        print(f"[SMTP SUCCESS] email sent -> {recipient}")
        return {"status": "SENT", "recipient": recipient}
    except Exception as exc:
        print(f"[SMTP ERROR] failed -> {recipient}: {exc}")
        logger.exception("Email dispatch failed to %s", recipient)
        return {"status": "FAILED", "recipient": recipient, "error": str(exc)}


def send_plain_email(recipient: str, subject: str, body: str) -> dict:
    """Generic send used for OTP verification and other non-SOS emails."""
    return _send(recipient, subject, body)


def send_otp_email(recipient: str, otp_code: str, expiry_minutes: int = 10) -> dict:
    subject = "Landslide Guardian — Email Verification Code"
    body = (
        "LANDSLIDE GUARDIAN — EMAIL VERIFICATION\n"
        "--------------------------------------\n\n"
        f"Your verification code is: {otp_code}\n\n"
        f"This code expires in {expiry_minutes} minutes and is valid for a "
        "limited number of attempts.\n\n"
        "If you did not request this, you can ignore this email.\n\n"
        "This is required to activate your emergency landslide alert "
        "registration with the Landslide Guardian system."
    )
    return _send(recipient, subject, body)

def send_alert_email(recipient: str, location: str, message: str, risk_score=None, risk_level=None):
    host, user, password, port, sender = _get_smtp_config()

    if not (user and password):
        print(f"[SMTP WARNING] Credentials missing in .env. Simulated alert for: {recipient}")
        return {
            "status": "NOT_CONFIGURED",
            "recipient": recipient,
            "message": "SMTP credentials (SMTP_USER / SMTP_PASSWORD) are not configured in backend/.env."
        }

    subject = f"🚨 Landslide Guardian SOS Alert — {location}"
    score_line = f"Calculated Risk: {risk_score}% ({risk_level})" if risk_score is not None else "Emergency SOS Notification"

    body = f"""LANDSLIDE GUARDIAN — EARLY WARNING DISPATCH
------------------------------------------------------------
Target Location : {location}
Status          : {score_line}

ALERT DETAILS:
{message}

------------------------------------------------------------
This is an automated emergency verification alert from the Landslide Guardian System.
Follow official local disaster-management and evacuation instructions.
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Landslide Guardian <{sender}>"
    msg["To"] = recipient
    msg.set_content(body)

    try:
        print(f"[SMTP CONNECTING] Sending alert to {recipient} via {host}:{port}...")
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, password)
            server.send_message(msg)
        
        print(f"[SMTP SUCCESS] SOS Email successfully sent to -> {recipient}")
        return {"status": "SENT", "recipient": recipient}
    except Exception as exc:
        print(f"[SMTP ERROR] Failed sending to {recipient}: {exc}")
        logger.exception("Email dispatch failed to %s", recipient)
        return {"status": "FAILED", "recipient": recipient, "error": str(exc)}

def dispatch_email_sos(location: str, users: list, custom_msg: str = None, risk_score=None, risk_level=None):
    timestamp = datetime.now(timezone.utc).isoformat()
    message = custom_msg or (
        f"Landslide risk has reached the emergency notification threshold near {location}. "
        "Please move away from unstable slopes, drainage channels, and exposed cut slopes, "
        "and initiate local safety protocols immediately."
    )
    
    logs = []
    for user in users:
        email = user.get("email", "") if isinstance(user, dict) else str(user)
        if not email:
            continue
        
        name = user.get("name", "Resident / Responder") if isinstance(user, dict) else "Resident"
        result = send_alert_email(email, location, message, risk_score, risk_level)
        logs.append({
            "name": name,
            "email": email,
            **result,
            "timestamp": timestamp,
        })

    statuses = [x["status"] for x in logs]
    if not logs:
        status = "NO_RECIPIENTS"
    elif any(s == "SENT" for s in statuses):
        status = "SENT"
    elif all(s == "NOT_CONFIGURED" for s in statuses):
        status = "SMTP_NOT_CONFIGURED"
    else:
        status = "FAILED"

    return {
        "status": status,
        "location": location,
        "recipient_count": len(logs),
        "timestamp": timestamp,
        "logs": logs,
        "smtp_configured": _smtp_configured(),
        "note": "Ensure SMTP_USER and SMTP_PASSWORD (Google App Password) are set in backend/.env"
    }