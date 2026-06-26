"""Git-AI Worker API 路由"""
import json
import time
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file
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
    """上传 metrics 数据 - 仅保存原始数据，由定时任务处理"""
    errors = []
    try:
        data = request.get_json()

        # 验证版本
        version = data.get('v', 1)

        events = data.get('events', [])
        if not events:
            return jsonify({
                'success': True,
                'errors': errors,
                'event_count': 0,
                'message': 'No events to process'
            }), 200

        # 仅保存原始数据到 metrics_events_raw
        # extract=0 表示未提取，由定时任务处理
        from core.database import MetricsDatabase

        db = MetricsDatabase()
        received_at = int(time.time() * 1000)
        payload_json = json.dumps(data)

        raw_id = db.save_metrics_raw(
            version=version,
            event_count=len(events),
            payload_json=payload_json,
            received_at=received_at
        )

        logger.info(f'Metrics raw data received: raw_id={raw_id}, events={len(events)}')

        return jsonify({
            'success': True,
            'errors': errors,
            'raw_id': raw_id,
            'message': 'Metrics raw data received, processing scheduled',
            'received_at': received_at
        }), 200

    except Exception as e:
        logger.error(f'Metrics upload error: {e}', exc_info=True)
        if events:
            for index in range(len(events)):
                errors.append({'index': index, 'error': str(e)})
                
        return jsonify({
            'success': False,
            'errors': errors,
            'error': str(e)
        }), 500


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
        service = OAuthService()
        result = service.create_device_code()

        logger.info(f'Device code created: {result["device_code"]}')

        return jsonify(result), 200

    except Exception as e:
        logger.error(f'Device code error: {e}')
        return jsonify({'error': str(e)}), 500


@oauth_bp.route('/verify_device')
def verfiy_device():
    try:
        return jsonify({'error': None})
    except Exception as e:
        logger.error(f'OAuth token error: {e}')
        return jsonify({
            'error': None,
            'error_description': str(e)
        }), 500
        

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
    try:
        channels = _release_service().list_channel_metadata()

        return jsonify({'channels': channels}), 200

    except Exception as e:
        logger.error(f'Releases API error: {e}')
        return jsonify({'error': str(e)}), 500


def _release_service():
    from core.services.release_service import ReleaseService

    return ReleaseService()


@releases_bp.route('/<channel>/download/<path:filename>', methods=['GET'])
def download_release_artifact(channel, filename):
    try:
        artifact = _release_service().get_active_artifact(channel, filename)
        if artifact is None:
            return jsonify({'error': 'Release artifact not found'}), 404
        response = send_file(
            BytesIO(artifact['content_blob']),
            mimetype=artifact['content_type'],
            as_attachment=True,
            download_name=artifact['filename'],
        )
        response.headers['ETag'] = f'"sha256:{artifact["sha256"]}"'
        response.headers['X-Git-AI-SHA256'] = artifact['sha256']
        return response
    except Exception as e:
        logger.error(f'Release artifact download error: {e}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@releases_bp.route('/admin/list', methods=['GET'])
def list_admin_releases():
    try:
        service = _release_service()
        releases = service.database.list_releases(
            channel=request.args.get('channel') or None,
            status=request.args.get('status') or None,
        )
        for release in releases:
            artifacts = service.database.list_artifacts(release['id'])
            release['artifact_count'] = len(artifacts)
            release['total_size_bytes'] = sum(item['size_bytes'] for item in artifacts)
        return jsonify({'success': True, 'releases': releases, 'data': {'releases': releases}}), 200
    except Exception as e:
        logger.error(f'Release admin list error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@releases_bp.route('/admin/<release_id>', methods=['GET'])
def get_admin_release(release_id):
    try:
        service = _release_service()
        release = service.database.get_release(release_id)
        if release is None:
            return jsonify({'success': False, 'error': 'Release not found'}), 404
        artifacts = service.database.list_artifacts(release_id)
        return jsonify({
            'success': True,
            'release': release,
            'artifacts': artifacts,
            'data': {'release': release, 'artifacts': artifacts},
        }), 200
    except Exception as e:
        logger.error(f'Release admin detail error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@releases_bp.route('/admin/upload', methods=['POST'])
def upload_admin_release():
    from core.services.release_service import ReleaseValidationError

    try:
        release = _release_service().create_release(
            tag=request.form.get('tag', ''),
            version=request.form.get('version'),
            channel=request.form.get('channel', ''),
            description=request.form.get('description'),
            created_by=request.headers.get('X-User') or request.headers.get('X-API-Key'),
            files=request.files.getlist('files'),
        )
        return jsonify({'success': True, 'release': release, 'data': {'release': release}}), 200
    except ReleaseValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Release admin upload error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@releases_bp.route('/admin/<release_id>/activate', methods=['POST'])
def activate_admin_release(release_id):
    try:
        release = _release_service().database.activate_release(release_id)
        if release is None:
            return jsonify({'success': False, 'error': 'Release not found'}), 404
        return jsonify({'success': True, 'release': release, 'data': {'release': release}}), 200
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 409
    except Exception as e:
        logger.error(f'Release admin activate error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@releases_bp.route('/admin/<release_id>', methods=['PUT'])
def update_admin_release(release_id):
    from core.services.release_service import ReleaseValidationError

    try:
        release = _release_service().update_release(
            release_id,
            tag=request.form.get('tag', ''),
            version=request.form.get('version'),
            channel=request.form.get('channel', ''),
            description=request.form.get('description'),
            files=request.files.getlist('files'),
        )
        if release is None:
            return jsonify({'success': False, 'error': 'Release not found'}), 404
        return jsonify({'success': True, 'release': release, 'data': {'release': release}}), 200
    except ReleaseValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f'Release admin update error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@releases_bp.route('/admin/<release_id>', methods=['DELETE'])
def delete_admin_release(release_id):
    try:
        deleted = _release_service().database.delete_release(release_id)
        if not deleted:
            return jsonify({'success': False, 'error': 'Release not found or active'}), 400
        return jsonify({'success': True}), 200
    except Exception as e:
        logger.error(f'Release admin delete error: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
