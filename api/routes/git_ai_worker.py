"""Git-AI Worker API 路由"""
from flask import Blueprint, request, jsonify
from core.config.logging import Logger
from core.middleware.auth import auth_required

# 创建蓝图
metrics_bp = Blueprint('metrics', __name__, url_prefix='/worker/metrics')
cas_bp = Blueprint('cas', __name__, url_prefix='/worker/cas')
oauth_bp = Blueprint('oauth', __name__, url_prefix='/worker/oauth')
releases_bp = Blueprint('releases', __name__, url_prefix='/worker/releases')

# 初始化日志记录器
logger = Logger.get_logger('api.git_ai_worker')

# ============ Metrics API ============

@metrics_bp.route('/upload', methods=['POST'])
# @auth_required
def metrics_upload():
    """上传 metrics 数据"""
    from core.services.metrics_service import MetricsService

    try:
        data = request.get_json()

        # 验证版本
        version = data.get('v', 1)
        if version != 1:
            return jsonify({
                'errors': [{'index': -1, 'error': f'Unsupported version: {version}'}]
            }), 400

        events = data.get('events', [])
        if not events:
            return jsonify({'errors': []}), 200

        # 处理 metrics
        service = MetricsService()
        errors = service.process_metrics_batch(events)

        logger.info(f'Metrics batch processed: {len(events)} events, {len(errors)} errors')

        return jsonify({'errors': errors}), 200

    except Exception as e:
        logger.error(f'Metrics upload error: {e}')
        return jsonify({'errors': [{'index': -1, 'error': str(e)}]}), 500


# ============ CAS API ============

@cas_bp.route('/upload', methods=['POST'])
# @auth_required
def cas_upload():
    """上传 CAS 对象"""
    from core.services.cas_service import CasService

    try:
        data = request.get_json()
        objects = data.get('objects', [])

        service = CasService()
        results = service.upload_objects(objects)

        logger.info(f'CAS upload: {results["success_count"]} success, {results["failure_count"]} failed')

        return jsonify(results), 200

    except Exception as e:
        logger.error(f'CAS upload error: {e}')
        return jsonify({
            'results': [],
            'success_count': 0,
            'failure_count': 0,
            'error': str(e)
        }), 500


@cas_bp.route('/', methods=['GET'])
# @auth_required
def cas_read():
    """读取 CAS 对象"""
    from core.services.cas_service import CasService

    try:
        hashes_param = request.args.get('hashes', '')
        hashes = [h.strip() for h in hashes_param.split(',') if h.strip()]

        if len(hashes) > 100:
            return jsonify({'error': 'Too many hashes, maximum 100 allowed'}), 400

        if not hashes:
            return jsonify({
                'results': [],
                'success_count': 0,
                'failure_count': 0
            }), 200

        service = CasService()
        results = service.read_objects(hashes)

        return jsonify(results), 200

    except Exception as e:
        logger.error(f'CAS read error: {e}')
        return jsonify({'error': str(e)}), 500


# ============ OAuth API ============

@oauth_bp.route('/device/code', methods=['POST'])
def device_code():
    """获取设备授权码"""
    from core.services.oauth_service import OAuthService

    try:
        data = request.get_json() or {}

        service = OAuthService()
        result = service.create_device_code()

        logger.info(f'Device code created: {result["device_code"]}')

        return jsonify(result), 200

    except Exception as e:
        logger.error(f'Device code error: {e}')
        return jsonify({'error': str(e)}), 500


@oauth_bp.route('/token', methods=['POST'])
def oauth_token():
    """交换令牌"""
    from core.services.oauth_service import OAuthService

    try:
        data = request.get_json()
        grant_type = data.get('grant_type')
        client_id = data.get('client_id')

        service = OAuthService()
        result = service.exchange_token(
            grant_type=grant_type,
            device_code=data.get('device_code'),
            refresh_token=data.get('refresh_token'),
            install_nonce=data.get('install_nonce'),
            client_id=client_id
        )

        logger.info(f'Token exchange: grant_type={grant_type}, success={not result.get("error")}')

        if result.get('error'):
            return jsonify(result), 400

        return jsonify(result), 200

    except Exception as e:
        logger.error(f'OAuth token error: {e}')
        return jsonify({
            'error': None,
            'error_description': str(e)
        }), 500


# ============ Releases API ============

@releases_bp.route('/', methods=['GET'])
def get_releases():
    """获取发布信息"""
    from core.config import ConfigLoader

    try:
        config = ConfigLoader().load()
        releases_config = config.get('git_ai', {}).get('releases', {})
        version = releases_config.get('version', '0.0.0')
        checksum = releases_config.get('checksum', '')

        channels = {
            'latest': {'version': version, 'checksum': checksum},
            'next': {'version': '', 'checksum': ''},
            'enterprise-latest': {'version': '', 'checksum': ''},
            'enterprise-next': {'version': '', 'checksum': ''}
        }

        return jsonify({'channels': channels}), 200

    except Exception as e:
        logger.error(f'Releases API error: {e}')
        return jsonify({'error': str(e)}), 500
