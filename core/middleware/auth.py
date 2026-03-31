"""认证中间件"""
from functools import wraps
from flask import request, jsonify
import jwt
from core.config.logging import Logger
from core.config import load_config


def auth_required(f):
    """认证装饰器 - 支持 Authorization Header 或 X-API-Key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查 API Key（优先）
        api_key = request.headers.get('X-API-Key')
        if api_key:
            # 验证 API Key（从配置读取）
            config_key = load_config().get('git_ai', {}).get('api_key')
            if config_key and api_key == config_key:
                return f(*args, **kwargs)
            if not config_key:
                # 未配置则接受任意 API Key（开发模式）
                return f(*args, **kwargs)
            return jsonify({'error': 'Invalid API key'}), 401

        # 检查 Bearer Token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]  # 去掉 "Bearer " 前缀
            try:
                # 验证 JWT
                secret = load_config().get('git_ai', {}).get('oauth', {}).get('secret_key', 'secret')
                payload = jwt.decode(token, secret, algorithms=['HS256'])
                # 验证通过，继续处理
                request.headers.set('auth_user', payload)
                return f(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'error': 'Invalid token'}), 401

        # 都没有则返回 401（可选：开发模式下可以跳过）
        if load_config().get('web', {}).get('debug', False):
            # 开发模式允许跳过认证
            return f(*args, **kwargs)

        return jsonify({'error': 'Unauthorized'}), 401

    return decorated_function
