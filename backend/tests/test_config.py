from app.core.config import Settings, get_settings


def test_settings_has_default_app_name():
    s = Settings(_env_file=None)
    assert s.app_name == "TradingRader"


def test_settings_default_types():
    s = Settings(_env_file=None)
    assert isinstance(s.database_url, str)
    assert isinstance(s.redis_url, str)
    assert isinstance(s.secret_key, str)
    assert isinstance(s.access_token_expire_minutes, int)
    assert isinstance(s.youtube_api_key, str)
    assert isinstance(s.twitterapi_io_api_key, str)
    assert isinstance(s.jin10_mcp_server_url, str)
    assert isinstance(s.jin10_mcp_bearer_token, str)
    assert isinstance(s.jin10_mcp_protocol_version, str)
    assert isinstance(s.dev_account_email, str)
    assert isinstance(s.dev_account_display_name, str)
    assert isinstance(s.dev_account_password, str)


def test_settings_access_token_default():
    s = Settings(_env_file=None)
    assert s.access_token_expire_minutes == 43200


def test_settings_dev_account_defaults():
    s = Settings(_env_file=None)
    assert s.dev_account_email == "maben996@gmail.com"
    assert s.dev_account_display_name == "maben996"
    assert s.dev_account_password == ""


def test_settings_reads_from_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-from-env")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

    s = Settings(_env_file=None)

    assert s.secret_key == "test-secret-from-env"
    assert s.access_token_expire_minutes == 60


def test_settings_environment_overrides_default(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "my-youtube-key")
    monkeypatch.setenv("TWITTERAPI_IO_API_KEY", "my-twitterapi-key")
    monkeypatch.setenv("JIN10_MCP_BEARER_TOKEN", "my-jin10-token")

    s = Settings(_env_file=None)

    assert s.youtube_api_key == "my-youtube-key"
    assert s.twitterapi_io_api_key == "my-twitterapi-key"
    assert s.jin10_mcp_bearer_token == "my-jin10-token"


def test_get_settings_returns_same_instance():
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
