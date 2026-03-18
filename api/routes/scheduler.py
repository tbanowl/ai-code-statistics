from flask import Blueprint, jsonify
from core.scheduler.scheduler import AICodeScheduler

scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/api/v1/scheduler')

# 全局调度器实例
_global_scheduler = None


def get_scheduler():
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = AICodeScheduler()
    return _global_scheduler


@scheduler_bp.route('/jobs', methods=['GET'])
def get_jobs():
    """获取所有任务"""
    try:
        scheduler = get_scheduler()
        jobs = scheduler.get_all_jobs()

        return jsonify({
            'success': True,
            'data': {'jobs': jobs}
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scheduler_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id: str):
    """获取任务状态"""
    try:
        scheduler = get_scheduler()
        job = scheduler.get_job_status(job_id)

        if job is None:
            return jsonify({'success': False, 'error': '任务不存在'}), 404

        return jsonify({
            'success': True,
            'data': job
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
