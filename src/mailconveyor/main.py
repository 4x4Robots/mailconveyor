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
