## Roadmap for adding IDLE support (raw sockets + `select`)

### 1. Constraints

- `imaplib` supports sending arbitrary commands, including `IDLE`.
- It does not provide a high-level IDLE API.
- We can:
  - Keep a persistent `IMAP4_SSL` connection.
  - Send `IDLE`.
  - Use `select.select` on the underlying socket to wait for server responses.
  - On `EXISTS`/`RECENT`, exit IDLE, fetch new messages, then re-enter IDLE.

### 2. Design

- New module function: `idle_loop(account: AccountConfig) -> None` (sync).
- Async wrapper: `asyncio.to_thread(idle_loop, account)`.
- Inside `idle_loop`:
  - Connect and login once.
  - `select` mailbox.
  - Loop:
    - Send `IDLE` command.
    - Use `select.select([imap._sock], [], [], timeout)`:
      - If readable:
        - `imap._sock.recv(...)` to read server data.
        - Parse for lines containing `EXISTS` or `RECENT`.
        - When event detected:
          - Send `DONE` to exit IDLE.
          - Use normal `search`/`fetch` to get new messages.
          - Hand off messages to a callback (e.g. queue or direct call).
      - If timeout:
        - Send `DONE` to keep connection fresh and re-enter IDLE.
  - On error:
    - Log, close connection, maybe reconnect with backoff.

### 3. Integration with async workers

- Replace `imap_poll_worker` with `imap_idle_worker`:

  - `imap_idle_worker`:
    - Creates a queue: `asyncio.Queue`.
    - Starts a background thread running `idle_loop`, which pushes raw messages into the queue (e.g. via a callback that uses `asyncio.run_coroutine_threadsafe(queue.put(...), loop)`).
    - In the async worker:
      - `while True: raw = await queue.get(); await forward_message(account, raw)`.

- `run_account_worker`:

```python
async def run_account_worker(account: AccountConfig) -> None:
    if account.imap.use_idle:
        await imap_idle_worker(account)
    else:
        await imap_poll_worker(account)
```

### 4. Steps to implement

1. **Step 1:** Implement a synchronous `idle_loop` that:
   - Connects, logs in, selects mailbox.
   - Enters IDLE, logs any server responses, exits after timeout.
   - No forwarding yet—just logging.

2. **Step 2:** Detect `EXISTS` lines:
   - When a line like `* 23 EXISTS` appears, exit IDLE and fetch unseen messages.
   - Reuse `_fetch_sync` logic but without reconnecting each time.

3. **Step 3:** Integrate with async world:
   - Provide a callback interface: `on_new_message(raw_bytes)` from `idle_loop`.
   - In async worker, use a queue to receive messages from the thread.

4. **Step 4:** Add reconnection and error handling:
   - On socket error or IMAP error, close and reconnect with backoff.
   - Log all transitions.

5. **Step 5:** Make `use_idle` a per-account toggle and test with a real IMAP server.

If you want, next iteration we can sketch the concrete `idle_loop` implementation and the queue-based bridge to the async worker.
