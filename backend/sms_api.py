"""Authenticated SMS delivery for operational ICMS notifications."""
import os
import re
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from core import auth, db, write_audit

router = APIRouter(prefix="/api/sms", tags=["SMS"])
logger = logging.getLogger(__name__)

# SMS is an official outbound communications channel.  Students, parents and
# external users cannot send messages through the institution's Twilio number.
SMS_SENDER_OFFICES = {
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10,       # leadership and academic offices
    15, 16, 17, 18, 19, 20, 21,           # student-facing academic services
    22, 23, 24, 25, 26, 27, 28,           # finance, HR, administration and IT
    29, 30, 31, 34, 35,                   # campus operations and reception
}
E164_PHONE = re.compile(r"^\+[1-9]\d{7,14}$")

class SmsSendIn(BaseModel):
    to: str = Field(..., description="Recipient phone number in E.164 format")
    body: str = Field(..., min_length=1, max_length=1600)

    @field_validator("to")
    @classmethod
    def valid_recipient(cls, value: str) -> str:
        value = value.strip()
        if not E164_PHONE.fullmatch(value):
            raise ValueError("Recipient must be an E.164 phone number, e.g. +919876543210")
        return value

    @field_validator("body")
    @classmethod
    def valid_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("SMS body cannot be empty")
        return value


def _twilio_client() -> tuple[Client, str]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    if not account_sid or not auth_token or not from_number:
        raise HTTPException(503, "SMS service is not configured")
    return Client(account_sid, auth_token), from_number


def _send_with_twilio(to: str, message: str):
    client, from_number = _twilio_client()
    try:
        return client.messages.create(to=to, from_=from_number, body=message)
    except TwilioRestException as exc:
        logger.warning("Twilio SMS rejected: status=%s code=%s", exc.status, exc.code)
        raise HTTPException(502, "Twilio could not deliver this SMS. Check the recipient and Twilio configuration")


def _require_sender_office(ctx: dict):
    if ctx["office_n"] not in SMS_SENDER_OFFICES:
        raise HTTPException(403, "Your portal is not authorised to send SMS messages")


@router.post("/send")
def send_sms(body: SmsSendIn, ctx=Depends(auth), s=Depends(db)):
    """Send a single operational SMS and record its Twilio SID in the audit log."""
    _require_sender_office(ctx)
    sent = _send_with_twilio(body.to, body.body)

    write_audit(
        s, ctx["sub"], ctx.get("role", ""), ctx["office_n"], "sms.send",
        f"twilio-message:{sent.sid}", "", sent.status or "queued",
        f"Operational SMS sent to {body.to[-4:].rjust(len(body.to), '*')}",
    )
    return {"ok": True, "message_sid": sent.sid, "status": sent.status}
