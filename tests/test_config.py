from backend.config import Settings


def test_trusted_hosts_include_apex_wildcard_for_default_domains():
    settings = Settings(
        frontend_url="http://localhost:5174",
        api_base_url="http://localhost:8000",
    )

    hosts = settings.trusted_hosts

    assert "app.libertyplacehoa.com" in hosts
    assert "*.libertyplacehoa.com" in hosts
