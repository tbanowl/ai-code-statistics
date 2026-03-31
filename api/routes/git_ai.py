"""Git-AI 相关 API（用户界面端点）"""
from flask import Blueprint, jsonify, request
from core.database.models import TelemetryEnvelope
from core.database.telemetry_envelope_db import TelemetryEnvelopeDB
from core.config.logging import Logger

git_ai_bp = Blueprint('git_ai', __name__, url_prefix='/api/git-ai')

# 初始化日志记录器
logger = Logger.get_logger('api.git_ai')

@git_ai_bp.route('/dsn/store/')
def dsn():
    """
    git ai 收集的信息
    """
    try:
        headers = request.headers
        # Sentry sentry_version=7, sentry_key={public_key}, sentry_client=git-ai/{env!("CARGO_PKG_VERSION")}
        sentry_auth = headers.get('X-Sentry-Auth')
        logger.info(f"dsn sentry_auth: {sentry_auth}")

        data = request.get_json()
        envelope = TelemetryEnvelope(envelope_data=data)
        db = TelemetryEnvelopeDB()
        db.save_telemetry_envelope(envelope)

        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f'Metrics upload error: {e}', exc_info=True)
                
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
