from fastapi import HTTPException
import pyotp
import pytest

from backend.api import auth as auth_api
from backend.models.models import User
from backend.schemas.schemas import TokenRefreshRequest, TwoFactorVerifyRequest


def test_login_requires_two_factor_code_when_enabled(db_session, create_user):
    user = create_user(email="twofa@example.com")
    secret = pyotp.random_base32()
    user_db = db_session.get(User, user.id)
    user_db.two_factor_secret = secret
    user_db.two_factor_enabled = True
    db_session.add(user_db)
    db_session.commit()

    form_missing = auth_api.OAuth2PasswordRequestFormWithOTP(
        grant_type="password",
        username="twofa@example.com",
        password="changeme",
        scope="",
        client_id=None,
        client_secret=None,
        otp=None,
    )
    with pytest.raises(HTTPException) as exc:
        auth_api.login(form_missing, db_session)
    assert exc.value.status_code == 401

    otp = pyotp.TOTP(secret).now()
    form_with_otp = auth_api.OAuth2PasswordRequestFormWithOTP(
        grant_type="password",
        username="twofa@example.com",
        password="changeme",
        scope="",
        client_id=None,
        client_secret=None,
        otp=otp,
    )
    token = auth_api.login(form_with_otp, db_session)
    assert token.access_token
    assert token.refresh_token


def test_refresh_token_flow_returns_new_tokens(db_session, create_user):
    user = create_user(email="refresh@example.com", role_name="SYSADMIN")

    form = auth_api.OAuth2PasswordRequestFormWithOTP(
        grant_type="password",
        username=user.email,
        password="changeme",
        scope="",
        client_id=None,
        client_secret=None,
        otp=None,
    )
    initial = auth_api.login(form, db_session)

    payload = TokenRefreshRequest(refresh_token=initial.refresh_token)
    refreshed = auth_api.refresh_token(payload, db_session)

    assert isinstance(refreshed.access_token, str) and len(refreshed.access_token) > 20
    assert isinstance(refreshed.refresh_token, str) and len(refreshed.refresh_token) > 20


def test_two_factor_setup_enable_and_disable(db_session, create_user):
    user = create_user(email="setup@example.com")

    setup_response = auth_api.setup_two_factor(db_session, current_user=user)
    assert setup_response.secret
    assert setup_response.otpauth_url

    stored = db_session.get(User, user.id)
    assert stored.two_factor_secret == setup_response.secret
    assert stored.two_factor_enabled is False

    otp = pyotp.TOTP(setup_response.secret).now()
    auth_api.enable_two_factor(
        TwoFactorVerifyRequest(otp=otp),
        db_session,
        current_user=user,
    )

    refreshed = db_session.get(User, user.id)
    assert refreshed.two_factor_enabled is True

    otp_disable = pyotp.TOTP(setup_response.secret).now()
    auth_api.disable_two_factor(
        TwoFactorVerifyRequest(otp=otp_disable),
        db_session,
        current_user=user,
    )

    disabled = db_session.get(User, user.id)
    assert disabled.two_factor_enabled is False
    assert disabled.two_factor_secret is None
