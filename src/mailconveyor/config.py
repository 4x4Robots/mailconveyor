import yaml
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

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
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(data)
