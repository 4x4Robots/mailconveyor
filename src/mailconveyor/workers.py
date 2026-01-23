import asyncio
import logging
from config import AccountConfig
from imap_client import fetch_new_messages
from forwarder import forward_message

logger = logging.getLogger(__name__)

async def imap_poll_worker(account: AccountConfig) -> None:
    logger.info("Starting poll worker for %s", account.name)

    while True:
        try:
            messages = await fetch_new_messages(account)
            if messages:
                logger.info("Account %s: %d new messages", account.name, len(messages))
            for uid, raw in messages:
                logger.debug("Processing message UID %s on %s", uid, account.name)
                await forward_message(account, raw)
        except Exception:
            logger.exception("Error in worker for %s", account.name)

        await asyncio.sleep(account.imap.poll_interval_seconds)

async def run_account_worker(account: AccountConfig) -> None:
    if account.imap.use_idle:
        raise NotImplementedError("IDLE not implemented yet")
    else:
        await imap_poll_worker(account)
