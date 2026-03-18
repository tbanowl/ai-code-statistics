"""维度表 API 路由"""
from flask import Blueprint, request, jsonify
from core.database.factory import create_database
from core.config.loader import ConfigLoader
from core.config.logging import Logger


dimensions_bp = Blueprint('dimensions', __name__, url_prefix='/api/dimensions')

# 全局配置
config_loader = ConfigLoader()
config = config_loader.load()

# 初始化日志记录器
logger = Logger.get_logger('api.dimensions')


@dimensions_bp.route('/repos', methods=['GET'])
def get_repos():
    """获取仓库列表，支持分页和排序"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        sort = request.args.get('sort')

        # 参数验证
        if page < 1:
            return jsonify({
                'success': False,
                'error': 'page must be >= 1'
            }), 400
        if page_size < 1 or page_size > 100:
            return jsonify({
                'success': False,
                'error': 'page_size must be between 1 and 100'
            }), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_repos(page=page, page_size=page_size, sort=sort)

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid parameter: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f'获取仓库列表失败: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dimensions_bp.route('/repos/<repo_id>', methods=['GET'])
def get_repo(repo_id):
    """获取单个仓库详情"""
    try:
        database = create_database(config.get('database', {}))
        repo = database.get_metrics_repo(repo_id)

        if repo:
            return jsonify({
                'success': True,
                'data': repo
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Repo not found'
            }), 404

    except Exception as e:
        logger.error(f'获取仓库详情失败: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dimensions_bp.route('/repos/<repo_id>/contributors', methods=['GET'])
def get_repo_contributors_endpoint(repo_id):
    """获取指定仓库的所有作者"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_repo_contributors(
            repo_id=repo_id, page=page, page_size=page_size
        )

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取仓库作者列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/repos/sync', methods=['POST'])
def sync_repos():
    """手动触发仓库统计更新"""
    try:
        from core.scheduler.dimensions_task import DimensionsUpdateTask

        task = DimensionsUpdateTask(config)
        result = task.execute()

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f'同步仓库统计失败: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@dimensions_bp.route('/contributors', methods=['GET'])
def get_contributors():
    """获取作者列表，支持分页和排序"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        sort = request.args.get('sort')

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_contributors(page=page, page_size=page_size, sort=sort)

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取作者列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/contributors/<author>', methods=['GET'])
def get_contributor(author):
    """获取单个作者详情"""
    try:
        database = create_database(config.get('database', {}))
        contributor = database.get_metrics_contributor(author)

        if contributor:
            return jsonify({
                'success': True,
                'data': contributor
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Contributor not found'
            }), 404

    except Exception as e:
        logger.error(f'获取作者详情失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/contributors/<author>/repos', methods=['GET'])
def get_author_repos(author):
    """获取指定作者参与的所有仓库"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_repo_contributors(
            author=author, page=page, page_size=page_size
        )

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取作者仓库列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/contributors/sync', methods=['POST'])
def sync_contributors():
    """手动触发作者统计更新"""
    try:
        from core.scheduler.dimensions_task import DimensionsUpdateTask

        task = DimensionsUpdateTask(config)
        result = task.execute()

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f'同步作者统计失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/repo-contributors', methods=['GET'])
def get_repo_contributors_list():
    """获取仓库作者关联列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        repo_id = request.args.get('repo_id')
        author = request.args.get('author')

        if page < 1:
            return jsonify({'success': False, 'error': 'page must be >= 1'}), 400
        if page_size < 1 or page_size > 100:
            return jsonify({'success': False, 'error': 'page_size must be between 1 and 100'}), 400

        database = create_database(config.get('database', {}))
        result = database.get_metrics_repo_contributors(
            repo_id=repo_id, author=author, page=page, page_size=page_size
        )

        return jsonify({
            'success': True,
            'data': result['data'],
            'pagination': result['pagination']
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'获取仓库作者关联列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@dimensions_bp.route('/repo-contributors/sync', methods=['POST'])
def sync_repo_contributors():
    """手动触发关联表更新"""
    try:
        from core.scheduler.dimensions_task import DimensionsUpdateTask

        task = DimensionsUpdateTask(config)
        result = task.execute()

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f'同步仓库作者关联失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
