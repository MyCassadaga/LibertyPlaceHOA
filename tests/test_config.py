import pytest

from backend.config import Settings


def test_trusted_hosts_include_apex_wildcard_for_default_domains():
    settings = Settings(
        frontend_url="http://localhost:5174",
        api_base_url="http://localhost:8000",
    )

    hosts = settings.trusted_hosts

    assert "app.libertyplacehoa.com" in hosts
    assert "*.libertyplacehoa.com" in hosts


def test_sendgrid_requires_api_key_when_backend_enabled():
    with pytest.raises(ValueError, match="SENDGRID_API_KEY"):
        Settings(email_backend="sendgrid", sendgrid_api_key=None)
