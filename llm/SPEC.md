# Async IMAP-based mailing list forwarder

## 1. Goals

- Use an existing IMAP mailbox as input.
- Forward selected incoming messages to a list of recipients.
- Use:
  - JSON for configuration and recipients
  - Pydantic for validation
  - Standard library for IMAP/SMTP/email/async/logging
- Architecture:
  - Async worker per IMAP account (polling first, IDLE later)
  - Clear separation of config, IO, and forwarding logic
  - Structured logging

---

## 2. High-level architecture

### Modules

- `config.py`
  - Pydantic models for configuration.
  - JSON loader returning `AppConfig`.

- `logging_setup.py`
  - Central logging configuration using `logging.basicConfig`.

- `imap_client.py`
  - Async wrapper around `imaplib.IMAP4_SSL` using `asyncio.to_thread`.
  - Minimal implementation:
    - Polling using `UNSEEN` search.
    - Returns list of `(uid, raw_bytes)`.

- `smtp_client.py`
  - Async wrapper around `smtplib.SMTP` / `SMTP_SSL`.
  - Builds TLS context.
  - Sends `email.message.EmailMessage` instances.

- `forwarder.py`
  - Parses raw incoming messages using `email.parser.BytesParser`.
  - Determines recipients from config.
  - Builds outgoing `EmailMessage` with:
    - `From` = list address
    - `To` = recipients
    - `Reply-To` = original `From` (optional)
  - Calls `smtp_client.send_mail`.

- `workers.py`
  - Per-account async worker:
    - Polls IMAP for new messages.
    - For each message, calls `forwarder.forward_message`.
  - Later: IDLE worker variant.

- `main.py`
  - Loads config from `config.json`.
  - Sets up logging.
  - Starts one worker per account using `asyncio.gather`.

---

## 3. Configuration model

### JSON file: `config.json`

- Top-level:
  - `log_level`: string (`"DEBUG"`, `"INFO"`, …)
  - `accounts`: list of account configs

### Pydantic models

- `Recipient`
  - `email: EmailStr`
  - `name: Optional[str]`
  - `active: bool = True`

- `ListRule`
  - `name: str`
  - `recipients: List[Recipient]`

- `ImapSettings`
  - `host: str`
  - `port: int = 993`
  - `username: str`
  - `password: str`
  - `mailbox: str = "INBOX"`
  - `use_idle: bool = False`
  - `poll_interval_seconds: int = 30`

- `SmtpSettings`
  - `host: str`
  - `port: int = 587`
  - `username: str`
  - `password: str`
  - `use_tls: bool = True`
  - `from_address: EmailStr`
  - `from_name: Optional[str]`

- `AccountConfig`
  - `name: str`
  - `imap: ImapSettings`
  - `smtp: SmtpSettings`
  - `lists: List[ListRule]`

- `AppConfig`
  - `accounts: List[AccountConfig]`
  - `log_level: str = "INFO"`

---

## 4. Minimal workflows

### Step 1: Receive mails (polling)

- Worker:
  - Calls `fetch_new_messages(account)` periodically.
  - Logs each message UID.
  - No forwarding yet (or optional).

### Step 2: Send mails

- `smtp_client.send_mail(account, msg)`:
  - Uses SMTP settings from config.
  - Sends a simple test message.
  - Logs success/failure.

### Step 3: Forwarder

- `forwarder.forward_message(account, raw_bytes)`:
  - Parses incoming message.
  - Chooses `account.lists[0]` recipients where `active == True`.
  - Builds outgoing message and sends via `smtp_client`.

### Step 4: Polling vs IDLE

- `run_account_worker(account)`:
  - If `use_idle` is `False`: run polling worker.
  - If `use_idle` is `True`: run IDLE worker (to be implemented).

---

## 5. Logging

- Use `logging` module.
- Levels:
  - DEBUG: protocol details, UIDs, decisions.
  - INFO: startup, shutdown, messages forwarded.
  - WARNING/ERROR: connection issues, send failures.
- Format:
  - `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

---

## 6. Roadmap

1. Implement MVP with:
   - JSON config + Pydantic
   - Polling IMAP worker
   - Simple forwarder
   - SMTP sending
2. Add:
   - UID tracking instead of `UNSEEN` only
   - Basic error handling and reconnect logic
3. Implement IDLE support:
   - Use `imaplib` socket and `select.select`
   - Maintain persistent connection per account
   - On EXISTS, fetch and forward new messages
4. Add tests for:
   - Config validation
   - Forwarder logic (pure functions)
   - Basic integration with a test IMAP/SMTP server (optional)
