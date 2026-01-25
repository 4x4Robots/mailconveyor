"""
After loading the local config and reading the config.yaml file connect to the given IMAP server 
and print all emails which are in the INBOX.
"""

import imaplib  # tbd delete
import email  # tbd delete
import logging
import asyncio
from pathlib import Path
from config import load_config
from logging_setup import setup_logging
from workers import run_account_worker

logger = logging.getLogger(__name__)

async def main() -> None:
    print("=== main_imap_connection ===")
    config = load_config(Path("config.yaml"))
    setup_logging(config.log_level)

    logger.info(config)  # tbd delete (secret reveal)
    
    account = config.accounts[0]
    logger.info(f"username='{account.imap.username}' password='{account.imap.password}'")
    
    imap = imaplib.IMAP4_SSL(account.imap.host, account.imap.port, timeout=3)
    imap.login(account.imap.username, account.imap.password)
    imap.select(account.imap.mailbox)
    
    typ, msgnums = imap.search(None, "ALL")
    if typ != "OK":
        logger.warning("IMAP search failed: %s", typ)
        imap.logout()
        return

    for msgnum in msgnums[0].split():
        typ, data = imap.fetch(msgnum, "(RFC822)")
        
        message = email.message_from_bytes(data[0][1])  # type: ignore

        print(f"Message Number: {msgnum}")
        print(f"From: {message.get('From')}")
        print(f"To: {message.get('To')}")
        print(f"Date: {message.get('Date')}")
        print(f"Subject: {message.get('Subject')}")
        
        print("Content:")
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                print(part.as_string())


    #tasks = [
    #    asyncio.create_task(run_account_worker(acc))
    #    for acc in config.accounts
    #]
    #await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
