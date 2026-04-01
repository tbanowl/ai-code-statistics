import pytest

from core.services.oauth_service import OAuthService


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(
        "core.config.load_config",
        lambda: {
            "git_ai": {
                "oauth": {
                    "secret_key": "test-secret-key-32-bytes-long!!",
                    "token_expiry_hours": 1,
                    "refresh_token_expiry_days": 30,
                    "device_code_expiry_seconds": 900,
                    "device_code_check_interval": 5,
                }
            }
        },
    )
    return OAuthService()


def test_create_device_code(service):
    data = service.create_device_code()
    assert "device_code" in data
    assert "user_code" in data
    assert data["expires_in"] == 900
    assert data["interval"] == 5
    assert data["device_code"] in service.device_codes


def test_approve_device_code(service):
    info = service.create_device_code()
    assert service.approve_device_code(info["user_code"]) is True
    assert service.device_codes[info["device_code"]]["approved"] is True


def test_exchange_token_missing_device_code(service):
    result = service.exchange_token(
        grant_type="urn:ietf:params:oauth:grant-type:device_code",
        device_code=None,
        refresh_token=None,
        install_nonce=None,
        client_id=None,
    )
    assert result["error"] == "invalid_request"


def test_exchange_refresh_token(service):
    result = service.exchange_token(
        grant_type="refresh_token",
        device_code=None,
        refresh_token="r1",
        install_nonce=None,
        client_id="cli",
    )
    assert "access_token" in result
    assert "refresh_token" in result


def test_exchange_install_nonce(service):
    result = service.exchange_token(
        grant_type="install_nonce",
        device_code=None,
        refresh_token=None,
        install_nonce="n1",
        client_id="cli",
    )
    assert "access_token" in result
    assert "refresh_token" in result


def test_exchange_unsupported_grant_type(service):
    result = service.exchange_token(
        grant_type="unsupported",
        device_code=None,
        refresh_token=None,
        install_nonce=None,
        client_id=None,
    )
    assert result["error"] == "unsupported_grant_type"


def test_exchange_device_code_current_behavior_returns_tokens(service):
    info = service.create_device_code()
    result = service.exchange_token(
        grant_type="urn:ietf:params:oauth:grant-type:device_code",
        device_code=info["device_code"],
        refresh_token=None,
        install_nonce=None,
        client_id=None,
    )
    assert "access_token" in result
    assert "refresh_token" in result
