from flask import Blueprint, request, jsonify
from datetime import datetime
from core.scheduler.stats_task import AICodeStatsTask
from core.config.loader import ConfigLoader
from core.config.logging import Logger

stats_bp = Blueprint('stats', __name__, url_prefix='/api/stats')

# 全局配置
config_loader = ConfigLoader()
config = config_loader.load()

# 初始化日志记录器
logger = Logger.get_logger('api.stats')


@stats_bp.route('/analyze', methods=['POST'])
def analyze():
    """执行统计分析"""
    try:
        data = request.get_json()
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')

        if not start_date_str or not end_date_str:
            logger.warning('请求缺少开始或结束日期参数')
            return jsonify({'success': False, 'error': '请提供开始和结束日期'}), 400

        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

        # 获取仓库列表
        selected_departments = data.get('departments', [])
        repos = _get_filtered_repos(config, selected_departments)

        if not repos:
            logger.warning('没有可用的仓库进行统计')
            return jsonify({'success': False, 'error': '未配置任何仓库或选中的部门没有仓库'}), 400

        logger.info(f'开始统计分析: {len(repos)} 个仓库, 时间范围: {start_date} 至 {end_date}')

        # 执行统计
        task = AICodeStatsTask(config)
        results = task._calculate_stats(repos, start_date, end_date)

        logger.info(f'统计分析完成: 总行数={results["total_lines"]}, AI行数={results["total_ai_lines"]}')

        return jsonify({'success': True, 'data': results})

    except Exception as e:
        logger.error(f'统计分析失败: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@stats_bp.route('/latest', methods=['GET'])
def get_latest():
    """获取最新统计结果"""
    try:
        from core.database.factory import create_database
        db = create_database(config)
        latest = db.get_latest_stat()

        if latest is None:
            logger.debug('暂无统计数据')
            return jsonify({'success': False, 'error': '暂无统计数据'}), 404

        logger.debug('返回最新统计结果')
        return jsonify({'success': True, 'data': latest})

    except Exception as e:
        logger.error(f'获取最新统计结果失败: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@stats_bp.route('/history', methods=['GET'])
def get_history():
    """获取统计历史记录"""
    try:
        from core.database.factory import create_database

        db = create_database(config)
        start_str = request.args.get('start')
        end_str = request.args.get('end')
        limit = int(request.args.get('limit', 100))

        start = datetime.fromisoformat(start_str) if start_str else None
        end = datetime.fromisoformat(end_str) if end_str else None

        history = db.get_stats_history(start, end, limit)

        logger.debug(f'返回 {len(history)} 条历史记录')
        return jsonify({'success': True, 'data': history})

    except Exception as e:
        logger.error(f'获取历史记录失败: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@stats_bp.route('/<stat_id>', methods=['GET'])
def get_stat_by_id(stat_id: str):
    """获取指定统计详情"""
    try:
        from core.database.factory import create_database
        db = create_database(config)
        stat = db.get_stat_by_id(stat_id)

        if stat is None:
            logger.debug(f'统计记录不存在: {stat_id}')
            return jsonify({'success': False, 'error': '统计记录不存在'}), 404

        logger.debug(f'返回统计记录: {stat_id}')
        return jsonify({'success': True, 'data': stat})

    except Exception as e:
        logger.error(f'获取统计记录失败: {e}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def _get_filtered_repos(config, selected_departments):
    """根据部门过滤仓库"""
    repos_config = config.get('repos', {})
    all_repos = []

    if 'enabled_repos' in repos_config:
        all_repos.extend(repos_config['enabled_repos'])

    if 'departments' in repos_config:
        if selected_departments:
            for dept in selected_departments:
                if dept in repos_config['departments']:
                    all_repos.extend(repos_config['departments'][dept])
        else:
            for dept_repos in repos_config['departments'].values():
                all_repos.extend(dept_repos)

    return all_repos
