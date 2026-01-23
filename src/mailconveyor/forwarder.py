import logging
from email.parser import BytesParser
from email.policy import default
from email.message import EmailMessage
from config import AccountConfig
from smtp_client import send_mail

logger = logging.getLogger(__name__)

async def forward_message(account: AccountConfig, raw: bytes) -> None:
    original = BytesParser(policy=default).parsebytes(raw)

    recipients = [
        r.email for r in account.lists[0].recipients if r.active
    ]
    if not recipients:
        logger.info("No active recipients for account %s", account.name)
        return

    msg = EmailMessage()
    subject = original.get("Subject", "")
    msg["Subject"] = f"[Forwarded] {subject}"
    msg["From"] = account.smtp.from_address
    msg["To"] = ", ".join(recipients)

    if original.get("From"):
        msg["Reply-To"] = original["From"]

    body_part = original.get_body(preferencelist=("plain",))
    body_text = body_part.get_content() if body_part else ""

    msg.set_content(
        f"Forwarded message:\n\n"
        f"From: {original.get('From')}\n"
        f"Subject: {subject}\n\n"
        f"{body_text}"
    )

    logger.info(
        "Forwarding message '%s' to %d recipients on account %s",
        subject, len(recipients), account.name
    )
    await send_mail(account, msg)
