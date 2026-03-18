"""测试 OAuthService"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from core.services.oauth_service import OAuthService


class TestOAuthService:
    """测试 OAuthService"""

    def test_create_device_code(self):
        """创建设备授权码"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()
            result = service.create_device_code()

            assert "device_code" in result
            assert "user_code" in result
            assert "verification_uri" in result
            assert "verification_uri_complete" in result
            assert result["expires_in"] > 0
            assert result["expires_in"] <= 900
            assert "interval" in result

            # 验证设备码格式 XXXX-XXXX
            user_code = result["user_code"]
            assert "-" in user_code
            parts = user_code.split("-")
            assert len(parts) == 2
            assert len(parts[0]) == 4
            assert len(parts[1]) == 4

            # 验证设备码已存储
            assert result["device_code"] in service.device_codes

    def test_create_device_code_with_custom_expiry(self):
        """使用自定义过期时间创建设备授权码"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            # 正确设置链式调用：ConfigLoader().load().get('git_ai', {}).get('oauth', {})
            mock_load_result = Mock()
            mock_load_result.get.return_value.get.return_value = {
                'device_code_expiry_seconds': 600,
                'device_code_check_interval': 10
            }
            mock_config_loader.return_value.load.return_value = mock_load_result

            service = OAuthService()
            result = service.create_device_code()

            assert result["expires_in"] == 600
            assert result["interval"] == 10

    def test_exchange_token_for_device_code_not_approved(self):
        """设备授权码未批准时返回 authorization_pending"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()
            device_code = service.create_device_code()["device_code"]

            result = service.exchange_token(
                grant_type='urn:ietf:params:oauth:grant-type:device_code',
                device_code=device_code,
                refresh_token=None,
                install_nonce=None,
                client_id=None
            )

            assert result["error"] == "authorization_pending"

    def test_exchange_token_for_approved_device_code(self):
        """已批准的设备授权码交换成功"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()
            device_code_info = service.create_device_code()
            device_code = device_code_info["device_code"]

            # 批准设备码
            service.approve_device_code(device_code_info["user_code"])

            result = service.exchange_token(
                grant_type='urn:ietf:params:oauth:grant-type:device_code',
                device_code=device_code,
                refresh_token=None,
                install_nonce=None,
                client_id=None
            )

            assert "access_token" in result
            assert result["token_type"] == "Bearer"
            assert "expires_in" in result
            assert "refresh_token" in result
            assert "refresh_expires_in" in result
            assert "error" not in result

            # 设备码应该已被清理
            assert device_code not in service.device_codes

    def test_exchange_token_for_invalid_device_code(self):
        """无效的设备授权码返回 invalid_grant"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()

            result = service.exchange_token(
                grant_type='urn:ietf:params:oauth:grant-type:device_code',
                device_code="invalid-device-code",
                refresh_token=None,
                install_nonce=None,
                client_id=None
            )

            assert result["error"] == "invalid_grant"

    def test_exchange_token_with_missing_device_code(self):
        """缺少 device_code 参数"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()

            result = service.exchange_token(
                grant_type='urn:ietf:params:oauth:grant-type:device_code',
                device_code=None,
                refresh_token=None,
                install_nonce=None,
                client_id=None
            )

            assert result["error"] == "invalid_request"

    def test_exchange_token_for_expired_device_code(self):
        """过期的设备授权码返回 expired_token"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            # 正确设置链式调用
            mock_load_result = Mock()
            mock_load_result.get.return_value.get.return_value = {
                'device_code_expiry_seconds': 0,
                'secret_key': 'test-secret-key-32-bytes-long!!'
            }
            mock_config_loader.return_value.load.return_value = mock_load_result

            service = OAuthService()
            # 先创建设备码
            device_code_info = service.create_device_code()
            device_code = device_code_info["device_code"]

            # 直接设置为过期状态
            from datetime import datetime, timedelta
            service.device_codes[device_code]["expires_at"] = datetime.now() - timedelta(seconds=1)

            result = service.exchange_token(
                grant_type='urn:ietf:params:oauth:grant-type:device_code',
                device_code=device_code,
                refresh_token=None,
                install_nonce=None,
                client_id=None
            )

            assert result["error"] == "expired_token"
            # 过期的设备码应该已被清理
            assert device_code not in service.device_codes

    def test_exchange_token_for_refresh_token(self):
        """使用 refresh_token 交换"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()

            result = service.exchange_token(
                grant_type='refresh_token',
                device_code=None,
                refresh_token='fake-refresh-token',
                install_nonce=None,
                client_id=None
            )

            assert "access_token" in result
            assert "refresh_token" in result
            assert "error" not in result

    def test_exchange_token_for_install_nonce(self):
        """使用 install_nonce 交换"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()

            result = service.exchange_token(
                grant_type='install_nonce',
                device_code=None,
                refresh_token=None,
                install_nonce='fake-nonce',
                client_id=None
            )

            assert "access_token" in result
            assert "refresh_token" in result
            assert "error" not in result

    def test_exchange_token_for_unsupported_grant_type(self):
        """不支持的授权类型"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()

            result = service.exchange_token(
                grant_type='unsupported_type',
                device_code=None,
                refresh_token=None,
                install_nonce=None,
                client_id=None
            )

            assert result["error"] == "unsupported_grant_type"
            assert "error_description" in result

    def test_approve_device_code(self):
        """批准设备授权码"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()
            device_code_info = service.create_device_code()
            user_code = device_code_info["user_code"]

            # 批准前应该未批准
            assert not service.device_codes[device_code_info["device_code"]]["approved"]

            # 批准
            result = service.approve_device_code(user_code)

            assert result is True

            # 批准后应该已批准
            assert service.device_codes[device_code_info["device_code"]]["approved"]

    def test_approve_device_code_invalid_user_code(self):
        """无效的用户验证码返回 False"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()

            result = service.approve_device_code("INVALID")

            assert result is False

    def test_generate_user_code_format(self):
        """用户验证码格式正确"""
        user_code = OAuthService._generate_user_code()

        # 验证格式 XXXX-XXXX
        assert "-" in user_code
        parts = user_code.split("-")
        assert len(parts) == 2
        assert len(parts[0]) == 4
        assert len(parts[1]) == 4

        # 验证只包含有效字符
        for char in user_code.replace("-", ""):
            assert char in "BCDFGHJKLMNPQRSTVWXYZ23456789"

    def test_generate_tokens_with_custom_expiry(self):
        """使用自定义过期时间生成令牌"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            # 正确设置链式调用
            mock_load_result = Mock()
            mock_load_result.get.return_value.get.return_value = {
                'secret_key': 'test-secret-key-32-bytes-long!!',
                'token_expiry_hours': 2,
                'refresh_token_expiry_days': 30
            }
            mock_config_loader.return_value.load.return_value = mock_load_result

            service = OAuthService()
            tokens = service._generate_tokens('test-client')

            assert tokens["expires_in"] == 2 * 3600  # 2 hours
            assert tokens["refresh_expires_in"] == 30 * 86400  # 30 days

    def test_multiple_device_codes_independent(self):
        """多个设备授权码独立运行"""
        with patch('core.config.ConfigLoader') as mock_config_loader:
            mock_config_loader.return_value.load.return_value.get.return_value = {}

            service = OAuthService()

            # 创建两个不同的设备码
            device_info1 = service.create_device_code()
            device_info2 = service.create_device_code()

            assert device_info1["device_code"] != device_info2["device_code"]
            assert device_info1["user_code"] != device_info2["user_code"]

            # 只批准第一个
            service.approve_device_code(device_info1["user_code"])

            # 第一个应该成功，第二个应该 pending
            result1 = service.exchange_token(
                grant_type='urn:ietf:params:oauth:grant-type:device_code',
                device_code=device_info1["device_code"],
                refresh_token=None,
                install_nonce=None,
                client_id=None
            )

            result2 = service.exchange_token(
                grant_type='urn:ietf:params:oauth:grant-type:device_code',
                device_code=device_info2["device_code"],
                refresh_token=None,
                install_nonce=None,
                client_id=None
            )

            assert "access_token" in result1
            assert result2["error"] == "authorization_pending"
