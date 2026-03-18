from flask import Blueprint, jsonify
from core.config.loader import ConfigLoader

projects_bp = Blueprint('projects', __name__, url_prefix='/api/v1/projects')

config_loader = ConfigLoader()
config = config_loader.load()


@projects_bp.route('/', methods=['GET'])
def get_projects():
    """获取项目列表（按部门分组）"""
    try:
        repos_config = config.get('repos', {})

        departments = []
        repos_by_department = {}
        all_repos = []

        if 'departments' in repos_config:
            departments = list(repos_config['departments'].keys())
            repos_by_department = repos_config['departments']
            for dept_repos in repos_by_department.values():
                all_repos.extend(dept_repos)

        if 'enabled_repos' in repos_config:
            all_repos.extend(repos_config['enabled_repos'])

        return jsonify({
            'success': True,
            'data': {
                'departments': departments,
                'repos_by_department': repos_by_department,
                'all_repos': all_repos
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@projects_bp.route('/departments', methods=['GET'])
def get_departments():
    """获取部门列表"""
    try:
        repos_config = config.get('repos', {})
        departments = list(repos_config.get('departments', {}).keys())

        return jsonify({
            'success': True,
            'data': {'departments': departments}
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
