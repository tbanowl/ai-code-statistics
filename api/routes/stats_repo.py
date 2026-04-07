"""仓库和 SSH Key 管理 API 路由"""

from flask import Blueprint, jsonify, request
import logging

stats_repo_bp = Blueprint("stats_repo", __name__, url_prefix="/api/stats-repo")


# 辅助函数：获取数据库实例
def get_database():
    """获取数据库实例"""
    from core.database import StatsDatabase, BlameStatsDatabase

    return StatsDatabase(), BlameStatsDatabase()


# 辅助函数：获取服务实例
def get_services():
    """获取服务实例"""
    from core.services import SshKeyService

    ssh_key_service = SshKeyService()
    return ssh_key_service


# ============================================================================
# SSH Key 管理
# ============================================================================


@stats_repo_bp.route("/ssh-key", methods=["POST"])
def add_ssh_key():
    """上传/添加 SSH Key"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        key_name = data.get("key_name")
        public_key = data.get("public_key")
        private_key = data.get("private_key")

        # 验证必填字段
        if not key_name:
            return jsonify({"success": False, "error": "key_name 不能为空"}), 400
        if not private_key:
            return jsonify({"success": False, "error": "private_key 不能为空"}), 400

        ssh_key_service = get_services()

        # 添加 SSH Key
        result = ssh_key_service.add_ssh_key(key_name, public_key, private_key)

        return jsonify({"success": True, "data": {"ssh_key": result}})

    except Exception as e:
        logging.error("添加 SSH Key 失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


@stats_repo_bp.route("/ssh-keys", methods=["GET"])
def list_ssh_keys():
    """列出所有 SSH Keys"""
    try:
        ssh_key_service = get_services()
        keys = ssh_key_service.list_ssh_keys()

        return jsonify(
            {"success": True, "data": {"ssh_keys": keys, "count": len(keys)}}
        )

    except Exception as e:
        logging.error("列出 SSH Keys 失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


@stats_repo_bp.route("/ssh-key/<key_id>", methods=["DELETE"])
def delete_ssh_key(key_id):
    """删除 SSH Key"""
    try:
        if not key_id:
            return jsonify({"success": False, "error": "key_id 不能为空"}), 400

        ssh_key_service = get_services()
        result = ssh_key_service.delete_ssh_key(key_id)

        if not result:
            return jsonify({"success": False, "error": "SSH Key 不存在"}), 404

        return jsonify({"success": True, "message": "SSH Key 已删除"})

    except Exception as e:
        logging.error("删除 SSH Key 失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# 仓库管理
# ============================================================================


@stats_repo_bp.route("<repo_id>/ssh-status", methods=["GET"])
def get_repo_ssh_status(repo_id):
    """获取仓库 SSH Key 状态"""
    try:
        if not repo_id:
            return jsonify({"success": False, "error": "repo_id 不能为空"}), 400

        stats_db, blame_stats_db = get_database()

        repo = blame_stats_db.get_repository_by_id(repo_id)
        if not repo:
            return jsonify({"success": False, "error": "仓库不存在"}), 404

        return jsonify(
            {
                "success": True,
                "data": {
                    "repo_id": repo.id,
                    "repo_path": repo.repo_path,
                    "repo_name": repo.repo_name,
                    "repo_stats_flag": repo.repo_stats_flag,
                    "ssh_key_id": repo.ssh_key_id,
                    "has_ssh_key": bool(repo.ssh_key_id),
                },
            }
        )

    except Exception as e:
        logging.error("获取仓库 SSH 状态失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


@stats_repo_bp.route("<repo_id>/ssh-key", methods=["PUT"])
def update_repo_ssh_key(repo_id):
    """关联仓库的 SSH Key"""
    try:
        if not repo_id:
            return jsonify({"success": False, "error": "repo_id 不能为空"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        ssh_key_id = data.get("ssh_key_id")
        # 允许设置为 None（使用默认配置）

        _, blame_stats_db = get_database()

        # 验证仓库是否存在
        repo = blame_stats_db.get_repository_by_id(repo_id)
        if not repo:
            return jsonify({"success": False, "error": "仓库不存在"}), 404

        # 如果指定了 ssh_key_id，验证它是否存在
        if ssh_key_id:
            from core.services import SshKeyService

            ssh_key_service = SshKeyService()
            key = ssh_key_service.get_ssh_key(ssh_key_id)
            if not key:
                return jsonify({"success": False, "error": "SSH Key 不存在"}), 404

        # 更新仓库的 SSH Key
        result = blame_stats_db.update_repository_ssh_key(repo_id, ssh_key_id)

        return jsonify(
            {
                "success": result,
                "message": "仓库 SSH Key 已更新" if result else "更新失败",
            }
        )

    except Exception as e:
        logging.error("更新仓库 SSH Key 失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


@stats_repo_bp.route("<repo_id>/stats-flag", methods=["PUT"])
def update_repo_stats_flag(repo_id):
    """启用/禁用仓库统计"""
    try:
        if not repo_id:
            return jsonify({"success": False, "error": "repo_id 不能为空"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        repo_stats_flag = data.get("repo_stats_flag")
        if repo_stats_flag is None:
            return jsonify({"success": False, "error": "repo_stats_flag 不能为空"}), 400

        # 验证值只能是 0 或 1
        if repo_stats_flag not in [0, 1]:
            return jsonify(
                {"success": False, "error": "repo_stats_flag 只能是 0 或 1"}
            ), 400

        stats_db, blame_stats_db = get_database()

        # 验证仓库是否存在
        repo = blame_stats_db.get_repository_by_id(repo_id)
        if not repo:
            return jsonify({"success": False, "error": "仓库不存在"}), 404

        # 更新仓库的统计标志
        result = blame_stats_db.update_repository_stats_flag(repo_id, repo_stats_flag)

        return jsonify(
            {
                "success": result,
                "message": "仓库统计设置已更新" if result else "更新失败",
            }
        )

    except Exception as e:
        logging.error("更新仓库统计设置失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# 数据查询
# ============================================================================


@stats_repo_bp.route("/blame/repo/<repo_id>", methods=["GET"])
def get_repo_blame_stats(repo_id):
    """获取仓库归因统计数据"""
    try:
        if not repo_id:
            return jsonify({"success": False, "error": "repo_id 不能为空"}), 400

        # 获取查询参数
        start_date = request.args.get("start_date", type=int)
        end_date = request.args.get("end_date", type=int)

        _, blame_stats_db = get_database()

        stats = blame_stats_db.get_repo_blame_stats(repo_id, start_date, end_date)

        return jsonify(
            {
                "success": True,
                "data": {"stats": stats, "count": len(stats), "repo_id": repo_id},
            }
        )

    except Exception as e:
        logging.error("获取仓库归因统计数据失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


@stats_repo_bp.route("/blame/file/<repo_id>", methods=["GET"])
def get_file_blame_stats(repo_id):
    """获取文件归因统计数据"""
    try:
        if not repo_id:
            return jsonify({"success": False, "error": "repo_id 不能为空"}), 400

        # 获取查询参数
        stat_date = request.args.get("stat_date", type=str)

        stats_db, blame_stats_db = get_database()

        stats = blame_stats_db.get_file_blame_stats(repo_id, stat_date)

        return jsonify(
            {
                "success": True,
                "data": {"stats": stats, "count": len(stats), "repo_id": repo_id},
            }
        )

    except Exception as e:
        logging.error("获取文件归因统计数据失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


@stats_repo_bp.route("/blame/repo/<repo_id>/contributors", methods=["GET"])
def get_repo_contributor_stats(repo_id):
    """获取仓库贡献者归因统计数据"""
    try:
        if not repo_id:
            return jsonify({"success": False, "error": "repo_id 不能为空"}), 400

        # 获取查询参数
        stat_date = request.args.get("stat_date", type=int)

        stats_db, blame_stats_db = get_database()

        stats = blame_stats_db.get_repo_contributor_stats(repo_id, stat_date)

        return jsonify(
            {
                "success": True,
                "data": {"stats": stats, "count": len(stats), "repo_id": repo_id},
            }
        )

    except Exception as e:
        logging.error("获取仓库贡献者归因统计数据失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


@stats_repo_bp.route("/blame/repos", methods=["GET"])
def get_blame_repo_stats_list():
    try:
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        if page < 1 or not (1 <= page_size <= 100):
            return jsonify({"success": False, "error": "分页参数无效"}), 400

        _, blame_stats_db = get_database()
        result = blame_stats_db.get_blame_repo_stats_paginated(
            page=page,
            page_size=page_size,
            start_date=request.args.get("start_date", type=int),
            end_date=request.args.get("end_date", type=int),
            repo_id=request.args.get("repo_id"),
        )
        return jsonify(
            {
                "success": True,
                "data": result["items"],
                "pagination": {
                    "total": result["total"],
                    "page": result["page"],
                    "page_size": result["page_size"],
                },
            }
        )
    except Exception as e:
        logging.error("获取仓库归因统计列表失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


@stats_repo_bp.route("/<repo_id>/branch-configs", methods=["GET"])
def get_repo_branch_configs(repo_id):
    try:
        _, blame_stats_db = get_database()
        configs = blame_stats_db.get_repo_branch_configs(repo_id)
        return jsonify(
            {"success": True, "data": {"configs": configs, "count": len(configs)}}
        )
    except Exception as e:
        logging.error("获取仓库分支配置失败", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500
