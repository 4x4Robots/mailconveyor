import smtplib
import ssl
import asyncio
import logging
from email.message import EmailMessage
from config import AccountConfig

logger = logging.getLogger(__name__)

async def send_mail(account: AccountConfig, msg: EmailMessage) -> None:
    await asyncio.to_thread(_send_sync, account, msg)

def _send_sync(account: AccountConfig, msg: EmailMessage) -> None:
    context = ssl.create_default_context()
    logger.debug("Connecting to SMTP %s", account.smtp.host)

    if account.smtp.use_tls:
        server = smtplib.SMTP(account.smtp.host, account.smtp.port)
        server.starttls(context=context)
    else:
        server = smtplib.SMTP_SSL(account.smtp.host, account.smtp.port, context=context)

    server.login(account.smtp.username, account.smtp.password)
    server.send_message(msg)
    server.quit()
    logger.info("Sent message to %s", msg["To"])
