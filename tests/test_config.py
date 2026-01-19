from backend.config import Settings


def test_trusted_hosts_include_apex_wildcard_for_default_domains():
    settings = Settings(
        frontend_url="http://localhost:5174",
        api_base_url="http://localhost:8000",
    )

    hosts = settings.trusted_hosts

    assert "app.libertyplacehoa.com" in hosts
    assert "*.libertyplacehoa.com" in hosts


def test_defaults_use_smtp_backend(monkeypatch):
    monkeypatch.delenv("EMAIL_BACKEND", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("EMAIL_HOST", raising=False)
    settings = Settings(_env_file=None)

    assert settings.email_backend == "smtp"
    assert settings.email_host == "smtp.gmail.com"
