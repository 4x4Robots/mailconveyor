from pathlib import Path

from mailconveyor.config import AppConfig, load_config


def test_load_config_from_example(project_root: Path):
    """Validate the current config.yaml.example file with the AppConfig class."""
    # load config file
    path_config = project_root / "config.yaml.example"
    config = load_config(path_config)

    # top-level
    assert config.log_level == "INFO"

    # accounts
    assert len(config.accounts) == 1
    acct = config.accounts[0]
    assert acct.name == "Example Account"

    # imap
    assert acct.imap.host == "imap.gmail.com"
    assert acct.imap.port == 993
    assert acct.imap.username == "your-email@gmail.com"
    assert acct.imap.password == "your-app-password"
    assert acct.imap.mailbox == "INBOX"
    assert acct.imap.use_idle is False
    assert acct.imap.poll_interval_seconds == 30

    # smtp
    assert acct.smtp.host == "smtp.gmail.com"
    assert acct.smtp.port == 587
    assert acct.smtp.username == "your-email@gmail.com"
    assert acct.smtp.password == "your-app-password"
    assert acct.smtp.use_tls is True
    assert acct.smtp.from_address == "your-email@gmail.com"
    assert acct.smtp.from_name == "Your Name"

    # lists
    assert len(acct.lists) == 1
    lst = acct.lists[0]
    assert lst.name == "Team"
    assert len(lst.recipients) == 2
    r0 = lst.recipients[0]
    assert r0.email == "person1@example.com"
    assert r0.name == "Person 1"
    assert r0.active is True
    r1 = lst.recipients[1]
    assert r1.email == "person2@example.com"
    assert r1.name == "Person 2"
    assert r1.active is True
