"""OAuth 设备授权流程服务"""
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional
from core.config.logging import Logger
from core.middleware.auth import DEFAULT_AUTH_SECRET_KEY


class OAuthService:
    """OAuth 设备授权流程服务"""

    def __init__(self):
        self.logger = Logger.get_logger('services.oauth')
        # 存储设备授权码状态（生产环境应该使用 Redis）
        self.device_codes = {}

        from core.config import load_config
        self.config = load_config().get('git_ai', {}).get('oauth', {})

    def create_device_code(self) -> Dict:
        """创建设备授权码"""
        device_code = secrets.token_urlsafe(32)

        expires_in = self.config.get('device_code_expiry_seconds', 900)
        interval = self.config.get('device_code_check_interval', 5)

        self.device_codes[device_code] = {
            'user_code': self._generate_user_code(),
            'expires_at': datetime.now() + timedelta(seconds=expires_in),
            'approved': False,
            'interval': interval
        }

        # TODO: 从配置获取 verification_uri
        verification_uri = 'http://localhost:8888/worker/oauth/verify_device'

        return {
            'device_code': device_code,
            'user_code': self.device_codes[device_code]['user_code'],
            'verification_uri': verification_uri,
            'verification_uri_complete': f'{verification_uri}?code={self.device_codes[device_code]["user_code"]}',
            'expires_in': expires_in,
            'interval': interval
        }

    def exchange_token(self, grant_type: str, device_code: Optional[str],
                      refresh_token: Optional[str], install_nonce: Optional[str],
                      client_id: Optional[str]) -> Dict:
        """交换令牌"""
        if grant_type == 'urn:ietf:params:oauth:grant-type:device_code':
            return self._exchange_device_code(device_code, client_id)
        elif grant_type == 'refresh_token':
            return self._exchange_refresh_token(refresh_token, client_id)
        elif grant_type == 'install_nonce':
            return self._exchange_install_nonce(install_nonce, client_id)
        else:
            return {
                'error': 'unsupported_grant_type',
                'error_description': f'不支持的授权类型: {grant_type}'
            }

    def _exchange_device_code(self, device_code: Optional[str], client_id: Optional[str]) -> Dict:
        """设备授权码交换令牌"""
        if not device_code:
            return {'error': 'invalid_request', 'error_description': '缺少 device_code'}

        auth = self.device_codes.get(device_code)

        if not auth:
            return {'error': 'invalid_grant', 'error_description': '无效的设备授权码'}

        if datetime.now() > auth['expires_at']:
            del self.device_codes[device_code]
            return {'error': 'expired_token', 'error_description': '设备授权码已过期'}

        if not auth['approved']:
            return {'error': 'authorization_pending', 'error_description': '用户尚未授权'}

        # 生成令牌
        tokens = self._generate_tokens(client_id or 'git-ai-cli')

        # 清理设备授权码
        del self.device_codes[device_code]

        return tokens

    def _exchange_refresh_token(self, refresh_token: Optional[str], client_id: Optional[str]) -> Dict:
        """刷新令牌交换"""
        if not refresh_token:
            return {'error': 'invalid_request', 'error_description': '缺少 refresh_token'}

        # 生产环境应该验证 refresh_token
        tokens = self._generate_tokens(client_id or 'git-ai-cli')
        return tokens

    def _exchange_install_nonce(self, install_nonce: Optional[str], client_id: Optional[str]) -> Dict:
        """安装 nonce 交换"""
        if not install_nonce:
            return {'error': 'invalid_request', 'error_description': '缺少 install_nonce'}

        # 生产环境应该验证 nonce
        tokens = self._generate_tokens(client_id or 'git-ai-cli')
        return tokens

    def _generate_tokens(self, client_id: str) -> Dict:
        """生成 access_token 和 refresh_token"""
        secret = self.config.get('secret_key', DEFAULT_AUTH_SECRET_KEY)

        now = datetime.now()
        access_expiry_hours = self.config.get('token_expiry_hours', 24)
        refresh_expiry_days = self.config.get('refresh_token_expiry_days', 90)

        access_payload = {
            'sub': 'user_id',
            'email': 'user@example.com',
            'name': 'User Name',
            'orgs': [{'org_id': '1', 'org_name': 'Organization', 'org_slug': 'org', 'role': 'owner'}],
            'personal_org_id': '1',
            'exp': (now + timedelta(hours=access_expiry_hours)).timestamp(),
            'iat': now.timestamp()
        }

        refresh_payload = {
            'sub': 'user_id',
            'email': 'user@example.com',
            'exp': (now + timedelta(days=refresh_expiry_days)).timestamp(),
            'iat': now.timestamp()
        }

        access_token = jwt.encode(access_payload, secret, algorithm='HS256')
        refresh_token = jwt.encode(refresh_payload, secret, algorithm='HS256')

        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': access_expiry_hours * 3600,
            'refresh_token': refresh_token,
            'refresh_expires_in': refresh_expiry_days * 86400
        }

    @staticmethod
    def _generate_user_code() -> str:
        """生成类似 XXXX-XXXX 格式的用户验证码"""
        chars = 'BCDFGHJKLMNPQRSTVWXYZ23456789'
        code = ''.join(secrets.choice(chars) for _ in range(4))
        code += '-' + ''.join(secrets.choice(chars) for _ in range(4))
        return code

    def approve_device_code(self, user_code: str) -> bool:
        """用户授权批准设备授权码"""
        for device_code, auth in self.device_codes.items():
            if auth['user_code'] == user_code:
                auth['approved'] = True
                return True
        return False
