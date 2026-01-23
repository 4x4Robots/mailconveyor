import imaplib
import asyncio
import logging
from typing import List, Tuple
from config import AccountConfig

logger = logging.getLogger(__name__)

async def fetch_new_messages(account: AccountConfig) -> List[Tuple[str, bytes]]:
    return await asyncio.to_thread(_fetch_sync, account)

def _fetch_sync(account: AccountConfig) -> List[Tuple[str, bytes]]:
    logger.debug("Connecting to IMAP %s", account.imap.host)
    imap = imaplib.IMAP4_SSL(account.imap.host, account.imap.port)
    imap.login(account.imap.username, account.imap.password)
    imap.select(account.imap.mailbox)

    typ, data = imap.search(None, "UNSEEN")
    if typ != "OK":
        logger.warning("IMAP search failed: %s", typ)
        imap.logout()
        return []

    uids = data[0].split()
    messages: List[Tuple[str, bytes]] = []

    for uid in uids:
        typ, msg_data = imap.fetch(uid, "(RFC822)")
        if typ == "OK" and msg_data and msg_data[0]:
            raw = msg_data[0][1]
            messages.append((uid.decode(), raw))
        else:
            logger.warning("Failed to fetch UID %s", uid)

    imap.logout()
    return messages
