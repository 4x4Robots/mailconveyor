from pathlib import Path

from mailconveyor.local_config import Settings


def test_settings_loads_from_env_example(pytestconfig, monkeypatch):
    # Ensure environment variables do not override the example file
    for key in ("DATABASE_URL", "REDIS_URL", "API_KEY"):
        monkeypatch.delenv(key, raising=False)

    env_path = Path(pytestconfig.rootpath).resolve() / ".env.example"
    assert str(env_path).endswith("mailconveyor/.env.example")
    
    settings = Settings(_env_file=env_path)

    assert settings.database_url == "postgresql://user:pass@localhost/db"
    assert settings.redis_url == "redis://localhost:6379"
    assert settings.api_key == "your-api-key-here"
