# IMAP IDLE vs SMTP for Mailing

> Is it possible, that an IMAP mail account notifies my mail program when a
> new mail arrived or is it only possible using polling? I'm looking into
> building a small mailing list service like mailman or majordomo.

You *can* build a lightweight mailing‑list‑style forwarder on top of an existing IMAP account — and your reasoning is solid. Using a hosted mailbox gives you:

- built‑in spam filtering  
- DKIM/DMARC/SPF handled by the provider  
- no need to run an MTA  
- no need to expose ports or manage TLS certificates  

That’s a perfectly reasonable design for a small, low‑volume list.

But there are a few architectural realities worth understanding so you don’t run into surprises later.

---

# 📬 IMAP + IDLE works fine for your use case
If your goal is:

- “When a new mail arrives in this mailbox, fetch it and forward it to N recipients”

…then IMAP with **IDLE** is absolutely enough.  
You get near‑instant notifications, and you don’t need to poll aggressively.

### What you *lose* compared to SMTP ingestion
For your scenario, these tradeoffs are acceptable:

- You don’t get the original SMTP envelope (e.g., `RCPT TO:`).  
  → Usually fine if you only have one list address.
- You can’t do VERP or bounce tracking.  
  → Fine for a small list.
- You rely on the provider’s spam decisions.  
  → You *want* that.

For a small, friendly mailing list, these aren’t deal‑breakers.

---

# 🧠 The real challenge: **sending** the forwarded mails
Receiving via IMAP is easy.  
Forwarding is where people often get tripped up.

You have two options:

## Option A — Send using the same mailbox (SMTP submission)
You authenticate to the same provider’s SMTP server and send the forwarded messages.

Pros:
- Simple  
- Provider handles DKIM/DMARC/SPF  
- Looks like normal mail from that account  

Cons:
- Some providers dislike “bulk” sending from personal accounts  
- You may hit rate limits  
- If you forward the original message *as-is*, DMARC may break  
  (because you’re effectively spoofing the original sender)

### Workaround
Wrap the original message as an attachment (`message/rfc822`) or rewrite the envelope sender to your list address.

This is exactly what Mailman does.

---

## Option B — Use the provider’s “redirect” semantics
Some IMAP servers support the `REDIRECT` command (RFC 6851).  
This forwards the message *server-side* without you re‑sending it.

Pros:
- No SMTP sending from your code  
- Preserves original headers  
- Very efficient  

Cons:
- Not widely supported  
- DMARC may still break  
- You lose control over formatting and list headers  

Most hosted mailboxes (Gmail, Outlook.com, etc.) do **not** support this.

---

# 🧩 A clean architecture for your idea
This keeps things simple and avoids MTA complexity:

### 1. IMAP client with IDLE
- Connect to the mailbox  
- Enter IDLE  
- On `EXISTS`, fetch the new message  

### 2. Apply your routing logic
- Check sender  
- Check subject  
- Check list membership  
- Maybe add a small header like `X-List-Name: mylist`

### 3. Forward via SMTP submission
- Authenticate to the same mailbox  
- Send a new message with the original attached or embedded  
- Set `From:` to the list address  
- Set `Reply-To:` to the original sender (optional)

This avoids DMARC issues and keeps you compliant.

---

# 🧠 Why this is a reasonable design
You’re essentially building a **smart IMAP-based forwarder**, not a full mailing list manager.  
For small groups, this is absolutely fine and avoids the operational burden of running an MTA.

You get:

- no inbound SMTP  
- no spam headaches  
- no DKIM/DMARC setup  
- no server maintenance  
- no open ports  
- no Postfix/Exim configuration  
- no queue management  

And you still get near‑real‑time delivery.

---

If you want, I can sketch a minimal Python architecture using `imaplib` + `IDLE` and a clean SMTP submission pattern that avoids DMARC pitfalls.

> Let's take a step back and first plan the architecture and create a spec file which will
> help me later implement it with CoPilot in VSCode. Here are some additional points:
> - use JSON to store settings and recipients
> - use pydantic for validation
> - prepare the function to be asynchronus, use w worker pool for different imap accounts
> - start with a minimal working example: receiving mails from one account, then sending
>   mails, then implementing the forwarder and polling or IDLE mechanic
> - use the logging module to write debug and status logs.

Nice, this is a fun little system to design. Let’s make a spec that’s concrete enough to code against later, but still minimal.

---

## High-level overview

- **Goal:** Small async mailing-list forwarder using existing IMAP accounts.
- **Core responsibilities:**
  - **Ingest:** Watch one or more IMAP inboxes (polling or IDLE).
  - **Process:** Decide which messages to forward and to whom.
  - **Deliver:** Send via SMTP (likely same provider as IMAP account).
  - **Config:** JSON-based configuration, validated with Pydantic.
  - **Infra:** Async core with a worker pool per IMAP account, structured logging.

---

## Components

1. **Config layer**
   - **Responsibility:** Load JSON config, validate with Pydantic, expose typed settings.
   - **Artifacts:**
     - `config.json` (user-editable)
     - `config.py` (Pydantic models + loader)

2. **IMAP client**
   - **Responsibility:** Connect to IMAP, select mailbox, fetch new messages.
   - **Modes:**
     - Minimal: polling with interval.
     - Later: optional IDLE support.
   - **Artifacts:**
     - `imap_client.py` (async wrapper around chosen IMAP lib)

3. **SMTP client**
   - **Responsibility:** Send messages via authenticated SMTP submission.
   - **Artifacts:**
     - `smtp_client.py` (async send function, simple API)

4. **Forwarder logic**
   - **Responsibility:** Given a raw message + account config, decide recipients and construct outgoing message(s).
   - **Artifacts:**
     - `forwarder.py` (pure logic, testable)

5. **Worker orchestration**
   - **Responsibility:** For each IMAP account, run a worker that:
     - watches for new mail
     - hands messages to forwarder
     - uses SMTP client to send
   - **Artifacts:**
     - `workers.py` (per-account worker, global runner)

6. **Logging**
   - **Responsibility:** Centralized logging setup using `logging` module.
   - **Artifacts:**
     - `logging_setup.py` (configure log level, format, file/console handlers)

7. **Entry point**
   - **Responsibility:** Load config, init logging, start async event loop and workers.
   - **Artifacts:**
     - `main.py`

---

## Data model (Pydantic)

```python
# config.py
from pydantic import BaseModel, EmailStr, AnyUrl, Field
from typing import List, Optional
from pathlib import Path
import json

class Recipient(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    active: bool = True

class ListRule(BaseModel):
    name: str
    # minimal for now: forward everything to these recipients
    recipients: List[Recipient]

class ImapSettings(BaseModel):
    host: str
    port: int = 993
    username: str
    password: str
    mailbox: str = "INBOX"
    use_idle: bool = False
    poll_interval_seconds: int = 30

class SmtpSettings(BaseModel):
    host: str
    port: int = 587
    username: str
    password: str
    use_tls: bool = True
    from_address: EmailStr
    from_name: Optional[str] = None

class AccountConfig(BaseModel):
    name: str
    imap: ImapSettings
    smtp: SmtpSettings
    lists: List[ListRule]

class AppConfig(BaseModel):
    accounts: List[AccountConfig]
    log_level: str = Field(default="INFO")

def load_config(path: Path) -> AppConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)
```

---

## Example JSON config

```json
{
  "log_level": "DEBUG",
  "accounts": [
    {
      "name": "main-list-account",
      "imap": {
        "host": "imap.example.com",
        "port": 993,
        "username": "list@example.com",
        "password": "secret",
        "mailbox": "INBOX",
        "use_idle": false,
        "poll_interval_seconds": 20
      },
      "smtp": {
        "host": "smtp.example.com",
        "port": 587,
        "username": "list@example.com",
        "password": "secret",
        "use_tls": true,
        "from_address": "list@example.com",
        "from_name": "My List"
      },
      "lists": [
        {
          "name": "default",
          "recipients": [
            { "email": "alice@example.org", "name": "Alice", "active": true },
            { "email": "bob@example.org", "name": "Bob", "active": true }
          ]
        }
      ]
    }
  ]
}
```

---

## Minimal workflows

### 1. Minimal receiving (one account, polling)

**Flow:**

1. **Startup**
   - Load `AppConfig` from JSON.
   - Configure logging.
   - Start async event loop.

2. **Worker (single account)**
   - Connect to IMAP.
   - Select mailbox.
   - Periodically:
     - Check for new messages (e.g., by UID or unseen flag).
     - Fetch new messages (RFC822).
     - Log each received message (subject, from, UID).
   - Sleep `poll_interval_seconds`.

**Spec for worker function:**

```python
# workers.py
async def imap_poll_worker(account: AccountConfig) -> None:
    """
    - Connect to IMAP for given account.
    - Poll for new messages in configured mailbox.
    - For now: just log basic info about new messages.
    - Later: pass messages to forwarder.
    """
    ...
```

---

### 2. Sending mails (SMTP only, no forwarding logic yet)

**Flow:**

1. Add a simple `send_test_message(account: AccountConfig)` function.
2. Use SMTP settings from config.
3. Log success/failure.

**Spec:**

```python
# smtp_client.py
async def send_mail(
    account: AccountConfig,
    to_addresses: list[str],
    subject: str,
    body: str
) -> None:
    """
    - Use account.smtp settings.
    - Build a simple text/plain message.
    - Send via SMTP (TLS if configured).
    - Log result.
    """
    ...
```

---

### 3. Implement forwarder logic

**Flow:**

1. IMAP worker fetches raw message bytes.
2. Pass to `forwarder.forward_message(account, raw_message_bytes)`.
3. Forwarder:
   - Parse message (`email.message.EmailMessage`).
   - Decide which list(s) to use (for now: always first list).
   - Build new outgoing message:
     - `From:` = account.smtp.from_address
     - `To:` = list recipients
     - `Reply-To:` = original `From` (optional)
     - Include original message inline or as attachment.
   - Call `smtp_client.send_mail(...)`.

**Spec:**

```python
# forwarder.py
async def forward_message(account: AccountConfig, raw_message: bytes) -> None:
    """
    - Parse raw message.
    - Determine target list(s) (minimal: account.lists[0]).
    - Build outgoing message(s) with proper headers.
    - Use smtp_client.send_mail to deliver.
    - Log what was forwarded to whom.
    """
    ...
```

---

### 4. Polling vs IDLE

**Spec:**

- `ImapSettings.use_idle` controls behavior.
- For now:
  - If `use_idle == False`: use polling worker.
  - If `use_idle == True`: use IDLE-capable worker (to be implemented later).

```python
# workers.py
async def run_account_worker(account: AccountConfig) -> None:
    if account.imap.use_idle:
        await imap_idle_worker(account)
    else:
        await imap_poll_worker(account)
```

---

## Async orchestration and worker pool

- Use `asyncio` as base.
- For multiple accounts:
  - Create one task per account worker.
  - Optionally, inside each worker, use a small internal queue + processing tasks if you want more parallelism later.

```python
# main.py
import asyncio
from pathlib import Path
from config import load_config
from workers import run_account_worker
from logging_setup import setup_logging

async def main() -> None:
    config = load_config(Path("config.json"))
    setup_logging(config.log_level)

    tasks = [
        asyncio.create_task(run_account_worker(account))
        for account in config.accounts
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Logging

- Use `logging` module, configured once at startup.
- Log categories:
  - **DEBUG:** protocol details, message IDs, decisions.
  - **INFO:** startup, shutdown, messages forwarded, counts.
  - **WARNING/ERROR:** connection issues, send failures, parse errors.

```python
# logging_setup.py
import logging
from typing import Literal

def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
```

---

If you like this structure, next step could be: pick the IMAP/SMTP libraries (e.g. `aioimaplib` / `aiosmtplib` or a thin async wrapper around standard libs) and then we can turn each spec block into concrete code in small, testable steps.

You’re right to step back here—if you get the shape right now, the implementation will basically “fall out” later.

Here’s a compact, VS Code–friendly spec you can almost drop in as `SPEC.md` and code against.

---

## 1. Project goals

**Goal:**  
Small, async mailing-list forwarder built on top of existing IMAP accounts.

**Key properties:**

- **Config & data:** JSON files, validated with Pydantic.
- **Async core:** `asyncio` with a worker per IMAP account.
- **Phased implementation:**
  1. Receive mails from one account (polling).
  2. Send mails via SMTP.
  3. Implement forwarder logic.
  4. Add polling vs IDLE mechanics.
- **Observability:** `logging` module for debug + status logs.

---

## 2. Module layout

- `config.py`  
  Pydantic models + JSON loader.
- `logging_setup.py`  
  Central logging configuration.
- `imap_client.py`  
  Async IMAP wrapper (polling first, IDLE later).
- `smtp_client.py`  
  Async SMTP sender.
- `forwarder.py`  
  Pure logic: decide recipients, build outgoing messages.
- `workers.py`  
  Per-account worker orchestration (polling/IDLE + forwarding).
- `main.py`  
  Entry point: load config, init logging, start workers.

---

## 3. Configuration model (Pydantic + JSON)

### 3.1 Pydantic models

```python
# config.py
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from pathlib import Path
import json

class Recipient(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    active: bool = True

class ListRule(BaseModel):
    name: str
    # minimal: forward everything to these recipients
    recipients: List[Recipient]

class ImapSettings(BaseModel):
    host: str
    port: int = 993
    username: str
    password: str
    mailbox: str = "INBOX"
    use_idle: bool = False
    poll_interval_seconds: int = 30

class SmtpSettings(BaseModel):
    host: str
    port: int = 587
    username: str
    password: str
    use_tls: bool = True
    from_address: EmailStr
    from_name: Optional[str] = None

class AccountConfig(BaseModel):
    name: str
    imap: ImapSettings
    smtp: SmtpSettings
    lists: List[ListRule]

class AppConfig(BaseModel):
    accounts: List[AccountConfig]
    log_level: str = Field(default="INFO")

def load_config(path: Path) -> AppConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)
```

### 3.2 Example `config.json`

```json
{
  "log_level": "DEBUG",
  "accounts": [
    {
      "name": "main-list-account",
      "imap": {
        "host": "imap.example.com",
        "port": 993,
        "username": "list@example.com",
        "password": "secret",
        "mailbox": "INBOX",
        "use_idle": false,
        "poll_interval_seconds": 20
      },
      "smtp": {
        "host": "smtp.example.com",
        "port": 587,
        "username": "list@example.com",
        "password": "secret",
        "use_tls": true,
        "from_address": "list@example.com",
        "from_name": "My List"
      },
      "lists": [
        {
          "name": "default",
          "recipients": [
            { "email": "alice@example.org", "name": "Alice", "active": true },
            { "email": "bob@example.org", "name": "Bob", "active": true }
          ]
        }
      ]
    }
  ]
}
```

---

## 4. Logging

```python
# logging_setup.py
import logging

def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
```

Usage: called once in `main.py`, everything else uses `logging.getLogger(__name__)`.

---

## 5. Minimal working steps

### 5.1 Step 1: Receive mails from one account (polling)

**Responsibility:**  
Connect to IMAP, poll for new messages, log basic info.

```python
# imap_client.py
from typing import List, Tuple

async def fetch_new_messages(account: "AccountConfig") -> List[Tuple[str, bytes]]:
    """
    Return list of (message_id, raw_bytes) for new messages.
    Minimal version can:
      - track last seen UID or use UNSEEN
      - log what it does
    """
    ...
```

```python
# workers.py
import asyncio
import logging
from config import AccountConfig
from .imap_client import fetch_new_messages

logger = logging.getLogger(__name__)

async def imap_poll_worker(account: AccountConfig) -> None:
    """
    - Loop forever:
      - fetch_new_messages
      - log subject/from for each
      - sleep poll_interval_seconds
    """
    while True:
        try:
            messages = await fetch_new_messages(account)
            for msg_id, raw in messages:
                logger.info("Received message %s on account %s", msg_id, account.name)
        except Exception:
            logger.exception("Error in IMAP poll worker for %s", account.name)
        await asyncio.sleep(account.imap.poll_interval_seconds)
```

### 5.2 Step 2: Sending mails (SMTP)

**Responsibility:**  
Send a simple text mail using account’s SMTP settings.

```python
# smtp_client.py
from typing import List
from config import AccountConfig

async def send_mail(
    account: AccountConfig,
    to_addresses: List[str],
    subject: str,
    body: str
) -> None:
    """
    - Build a simple text/plain message.
    - Use account.smtp settings.
    - Send via SMTP (TLS if configured).
    - Log success/failure.
    """
    ...
```

You can test this independently with a small `async def main()` that just sends a test mail.

### 5.3 Step 3: Forwarder logic

**Responsibility:**  
Take raw incoming message, decide recipients, build outgoing message(s), call `send_mail`.

```python
# forwarder.py
from config import AccountConfig

async def forward_message(account: AccountConfig, raw_message: bytes) -> None:
    """
    - Parse raw_message with email.message_from_bytes.
    - For now: use account.lists[0].recipients where active == True.
    - Build outgoing message:
        From: account.smtp.from_address
        To: all recipients
        Reply-To: original From (optional)
        Body: include original message inline or as attachment.
    - Call smtp_client.send_mail.
    - Log what was forwarded to whom.
    """
    ...
```

Then wire it into the worker:

```python
# workers.py
from .forwarder import forward_message

async def imap_poll_worker(account: AccountConfig) -> None:
    ...
    messages = await fetch_new_messages(account)
    for msg_id, raw in messages:
        logger.info("Forwarding message %s on account %s", msg_id, account.name)
        await forward_message(account, raw)
```

### 5.4 Step 4: Polling vs IDLE

**Responsibility:**  
Switch behavior based on config flag; IDLE can be added later without touching the rest.

```python
# workers.py
async def imap_idle_worker(account: AccountConfig) -> None:
    """
    - Use IMAP IDLE to wait for EXISTS notifications.
    - On new mail: fetch and forward.
    - Same logging semantics as poll worker.
    """
    ...

async def run_account_worker(account: AccountConfig) -> None:
    if account.imap.use_idle:
        await imap_idle_worker(account)
    else:
        await imap_poll_worker(account)
```

---

## 6. Async orchestration and worker pool

```python
# main.py
import asyncio
from pathlib import Path
from config import load_config
from logging_setup import setup_logging
from workers import run_account_worker

async def main() -> None:
    config = load_config(Path("config.json"))
    setup_logging(config.log_level)

    tasks = [
        asyncio.create_task(run_account_worker(account))
        for account in config.accounts
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
```

This gives you:

- JSON + Pydantic config
- async worker per IMAP account
- clear extension points for IDLE, smarter routing, bounce handling later
- logging hooks everywhere

If you want, next step could be: pick concrete IMAP/SMTP libs and define the exact signatures for `fetch_new_messages` and `send_mail` so Copilot can autocomplete the rest in a pretty deterministic way.

> Alright, great work. I want to use as much standard library modules as possible.

If you want to lean heavily on the Python standard library, you’re in a very good place — this project maps surprisingly well to what the stdlib already gives you. The only external dependency you truly need is **Pydantic** for config validation. Everything else can be built on top of:

- `imaplib` (IMAP)
- `smtplib` + `email` (SMTP + message construction)
- `asyncio` (concurrency)
- `logging` (observability)
- `json` (config storage)
- `email.parser`, `email.message`, `email.policy` (parsing incoming mail)

Below is a refined architecture and spec that explicitly sticks to the standard library wherever possible.

---

# 📐 Architecture (stdlib‑first)

## Core modules

### 1. `config.py`
- Loads JSON config.
- Validates with Pydantic.
- Exposes typed settings.

### 2. `logging_setup.py`
- Configures logging once.
- Everything else uses `logging.getLogger(__name__)`.

### 3. `imap_client.py`
- Uses **`imaplib.IMAP4_SSL`**.
- Provides async wrappers using `asyncio.to_thread` for blocking calls.
- Implements:
  - minimal polling
  - later: IDLE (still possible with stdlib, but requires manual socket handling)

### 4. `smtp_client.py`
- Uses **`smtplib.SMTP`** or `SMTP_SSL`.
- Builds messages using `email.message.EmailMessage`.
- Sends via authenticated SMTP submission.

### 5. `forwarder.py`
- Pure logic.
- Parses raw message with `email.parser.BytesParser`.
- Builds outgoing message using stdlib `email` package.
- Calls `smtp_client.send_mail`.

### 6. `workers.py`
- Async worker per IMAP account.
- Polling loop:
  - fetch new messages
  - forward them
  - sleep
- Later: IDLE worker.

### 7. `main.py`
- Loads config.
- Sets up logging.
- Starts async workers.

---

# 🧱 Detailed spec (stdlib‑focused)

## 1. Config (JSON + Pydantic)

```python
# config.py
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from pathlib import Path
import json

class Recipient(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    active: bool = True

class ListRule(BaseModel):
    name: str
    recipients: List[Recipient]

class ImapSettings(BaseModel):
    host: str
    port: int = 993
    username: str
    password: str
    mailbox: str = "INBOX"
    use_idle: bool = False
    poll_interval_seconds: int = 30

class SmtpSettings(BaseModel):
    host: str
    port: int = 587
    username: str
    password: str
    use_tls: bool = True
    from_address: EmailStr
    from_name: Optional[str] = None

class AccountConfig(BaseModel):
    name: str
    imap: ImapSettings
    smtp: SmtpSettings
    lists: List[ListRule]

class AppConfig(BaseModel):
    accounts: List[AccountConfig]
    log_level: str = Field(default="INFO")

def load_config(path: Path) -> AppConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)
```

---

## 2. Logging

```python
# logging_setup.py
import logging

def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
```

---

## 3. IMAP client (stdlib)

### Key idea  
`imaplib` is blocking.  
To keep everything async, wrap blocking calls in `asyncio.to_thread`.

```python
# imap_client.py
import imaplib
import asyncio
import logging
from typing import List, Tuple
from config import AccountConfig

logger = logging.getLogger(__name__)

async def fetch_new_messages(account: AccountConfig) -> List[Tuple[str, bytes]]:
    """
    Returns list of (uid, raw_bytes) for new messages.
    Uses UNSEEN for minimal implementation.
    """
    return await asyncio.to_thread(_fetch_sync, account)

def _fetch_sync(account: AccountConfig) -> List[Tuple[str, bytes]]:
    imap = imaplib.IMAP4_SSL(account.imap.host, account.imap.port)
    imap.login(account.imap.username, account.imap.password)
    imap.select(account.imap.mailbox)

    typ, data = imap.search(None, "UNSEEN")
    if typ != "OK":
        return []

    uids = data[0].split()
    messages = []

    for uid in uids:
        typ, msg_data = imap.fetch(uid, "(RFC822)")
        if typ == "OK":
            raw = msg_data[0][1]
            messages.append((uid.decode(), raw))

    imap.logout()
    return messages
```

Later, you can add:

- UID tracking
- IDLE support (using `imap._sock` and manual reads)

All still stdlib.

---

## 4. SMTP client (stdlib)

```python
# smtp_client.py
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

    if account.smtp.use_tls:
        server = smtplib.SMTP(account.smtp.host, account.smtp.port)
        server.starttls(context=context)
    else:
        server = smtplib.SMTP_SSL(account.smtp.host, account.smtp.port, context=context)

    server.login(account.smtp.username, account.smtp.password)
    server.send_message(msg)
    server.quit()
```

---

## 5. Forwarder logic (stdlib email package)

```python
# forwarder.py
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

    msg = EmailMessage()
    msg["Subject"] = f"[Forwarded] {original.get('Subject', '')}"
    msg["From"] = account.smtp.from_address
    msg["To"] = ", ".join(recipients)
    msg["Reply-To"] = original.get("From")

    # simplest: inline the original
    msg.set_content(
        f"Forwarded message:\n\n"
        f"From: {original.get('From')}\n"
        f"Subject: {original.get('Subject')}\n\n"
        f"{original.get_body(preferencelist=('plain',)).get_content()}"
    )

    logger.info("Forwarding message to %d recipients", len(recipients))
    await send_mail(account, msg)
```

---

## 6. Worker orchestration (asyncio)

```python
# workers.py
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
            for uid, raw in messages:
                logger.debug("Received message UID %s", uid)
                await forward_message(account, raw)
        except Exception:
            logger.exception("Error in worker for %s", account.name)

        await asyncio.sleep(account.imap.poll_interval_seconds)

async def run_account_worker(account: AccountConfig) -> None:
    if account.imap.use_idle:
        # placeholder for later
        raise NotImplementedError("IDLE not implemented yet")
    else:
        await imap_poll_worker(account)
```

---

## 7. Entry point

```python
# main.py
import asyncio
from pathlib import Path
from config import load_config
from logging_setup import setup_logging
from workers import run_account_worker

async def main() -> None:
    config = load_config(Path("config.json"))
    setup_logging(config.log_level)

    tasks = [
        asyncio.create_task(run_account_worker(acc))
        for acc in config.accounts
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
```

---

# 🎯 Why this design works well with stdlib

- **No external IMAP/SMTP libraries**  
  Everything is built on top of `imaplib` and `smtplib`, wrapped in `asyncio.to_thread` for concurrency.

- **No external email parsing libraries**  
  The stdlib `email` package is powerful and standards‑compliant.

- **Async without external frameworks**  
  `asyncio` gives you worker pools and concurrency.

- **Logging is fully stdlib**  
  No need for structlog or loguru unless you want them later.

- **Config is JSON**  
  Easy to edit, easy to validate with Pydantic.

---

If you want, I can now generate:

- a `SPEC.md` file ready to drop into your repo  
- a minimal working prototype (MVP) using only stdlib + Pydantic  
- a roadmap for adding IDLE support using raw sockets and `select`  

Just tell me which direction you want to take next.

