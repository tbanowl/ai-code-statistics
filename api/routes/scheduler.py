from flask import Blueprint, jsonify, request, current_app
from core.scheduler import AICodeScheduler
import logging

scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/api/v1/scheduler')

# logging = Logger.get_logger('api.scheduler')

def get_scheduler() -> AICodeScheduler:
    """
    获取调度器实例。
    如果 app.py 中已创建 scheduler 实例（当 scheduler.enabled=True 时），
    则使用该实例；否则返回 None。
    """
    # 尝试从 app 的上下文中获取 scheduler
    scheduler = current_app.config.get('_scheduler')
    if scheduler is None:
        raise Exception("scheduler 实例不存在")
    return scheduler


@scheduler_bp.route('/jobs', methods=['GET'])
def get_jobs():
    """获取所有任务"""
    try:
        scheduler = get_scheduler()
        if scheduler is None:
            return jsonify({'success': False, 'error': '调度器未启用'}), 503

        jobs = scheduler.get_all_jobs()

        return jsonify({
            'success': True,
            'data': {'jobs': jobs}
        })

    except Exception as e:
        logging.error('获取所有任务', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@scheduler_bp.route('/jobs/status', methods=['GET'])
def get_job():
    """获取任务状态"""
    try:
        job_id = request.args.get("jobId")
        if not job_id:
            return jsonify({'success': False, 'error': 'jobId 不能为空'})
        scheduler = get_scheduler()
        if scheduler is None:
            return jsonify({'success': False, 'error': '调度器未启用'}), 503

        job = scheduler.get_job_status(job_id)

        if job is None:
            return jsonify({'success': False, 'error': '任务不存在'}), 404

        return jsonify({
            'success': True,
            'data': job
        })

    except Exception as e:
        logging.error('获取任务状态失败', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@scheduler_bp.route('/jobs/trigger', methods=['POST'])
def trigger_job():
    """手动触发任务"""
    try:
        job_id = request.args.get("jobId")
        if not job_id:
            return jsonify({'success': False, 'error': 'jobId 不能为空'})
        scheduler = get_scheduler()
        if scheduler is None:
            return jsonify({'success': False, 'error': '调度器未启用'})

        # 检查任务是否在注册表中
        from core.scheduler.registry import TaskRegistry
        task_class = TaskRegistry.get(job_id)
        if not task_class:
            return jsonify({'success': False, 'error': '任务不存在'}), 404

        # 触发任务
        execution_id = scheduler.trigger_job_with_execution(job_id)
        if execution_id is None:
            running = scheduler.scheduler_db.get_running_task_execution(job_id)
            if running:
                return jsonify({'success': False, 'error': '任务正在运行'}), 409
            return jsonify({'success': False, 'error': '触发任务失败'}), 500

        return jsonify({
            'success': True,
            'data': {
                'status': 'pending',
                'job_id': job_id,
                'execution_id': execution_id,
            }
        })

    except Exception as e:
        logging.error('手动触发任务失败', e)
        return jsonify({'success': False, 'error': str(e)})


@scheduler_bp.route('/jobs/history/executions', methods=['GET'])
def get_job_executions():
    """获取任务执行历史"""
    try:
        job_id = request.args.get("jobId")
        if not job_id:
            return jsonify({'success': False, 'error': 'jobId 不能为空'})
        scheduler = get_scheduler()
        if scheduler is None:
            return jsonify({'success': False, 'error': '调度器未启用'}), 503

        # 获取查询参数
        limit = min(request.args.get('limit', 10, type=int), 100)
        status = request.args.get('status', None)

        executions = scheduler.scheduler_db.get_task_executions(job_id, limit, status)

        return jsonify({
            'success': True,
            'data': {
                'executions': executions,
                'job_id': job_id,
                'count': len(executions)
            }
        })

    except Exception as e:
        logging.error('获取任务执行历史失败', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@scheduler_bp.route('/jobs/execution-detail', methods=['GET'])
def get_job_execution():
    """获取任务执行详情"""
    try:
        job_id = request.args.get("jobId")
        if not job_id:
            return jsonify({'success': False, 'error': 'jobId 不能为空'})
        execution_id = request.args.get("executionId")
        if not job_id:
            return jsonify({'success': False, 'error': 'executionId 不能为空'})
        scheduler = get_scheduler()

        execution = scheduler.scheduler_db.get_task_execution(execution_id)

        if not execution:
            return jsonify({'success': False, 'error': '执行记录不存在'}), 404

        # 验证 job_id 是否匹配
        if execution['job_id'] != job_id:
            return jsonify({'success': False, 'error': '执行记录不匹配'}), 400

        return jsonify({
            'success': True,
            'data': execution
        })

    except Exception as e:
        logging.error('获取任务执行详情失败', e)
        return jsonify({'success': False, 'error': str(e)}), 500
