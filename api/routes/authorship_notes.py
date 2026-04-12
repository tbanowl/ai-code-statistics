import os

from flask import Blueprint, request, jsonify
from core.config.logging import Logger
from core.middleware.auth import auth_required
from core.services.notes_service import NotesRestService

git_notes_rest_bp = Blueprint("notes_rest", __name__, url_prefix="/worker/notes")
authorship_notes_rest_bp = Blueprint(
    "authorship_notes_rest", __name__, url_prefix="/worker/authorship_notes"
)
logger = Logger.get_logger("api.notes")

service = NotesRestService(db_url=os.environ.get("DB_URL"))


def get_notes_service() -> NotesRestService:
    return service


def ok_response(data):
    """成功响应"""
    return jsonify({"ok": True, "data": data})


def error_response(message, status_code=400):
    """错误响应"""
    return jsonify({"ok": False, "error": message}), status_code


@git_notes_rest_bp.route("", methods=["PUT"])
@authorship_notes_rest_bp.route("", methods=["PUT"])
@auth_required
def create_or_update_note():
    """创建或更新单个注释 (PUT /worker/notes)

    请求:
    {
        "repo_url": "https://codeup.aliyun.com/org/repo.git",
        "branch": "main",
        "commit_sha": "abc123def456...",
        "note_blob_oid": "abdfadsfadfa...",
        "author_name": "John Doe",
        "author_email": "john@example.com",
        "content": "<authorship log content>"
    }

    响应 (200):
    {
        "ok": true,
        "data": { "id": "ctg3h1e..." }
    }
    """
    try:
        payload = request.get_json(silent=True)
        logger.info(f"put notes payload: {payload}")
        if not payload:
            return error_response("请求体不能为空", 400)

        required_fields = [
            "repo_url",
            "branch",
            "commit_sha",
            "author_name",
            "author_email",
            "content",
        ]
        for field in required_fields:
            if field not in payload:
                return error_response(f"缺少必需字段: {field}", 400)

        note = get_notes_service().create_or_update_note(
            repo_url=payload["repo_url"],
            branch=payload["branch"],
            commit_sha=payload["commit_sha"],
            note_blob_oid=payload.get("note_blob_oid"),
            original_commit_sha=payload.get("original_commit_sha"),
            content=payload["content"],
            author_name=payload["author_name"],
            author_email=payload["author_email"],
        )

        return ok_response({"id": note.id})

    except Exception as e:
        logger.error("创建或更新单个注释错误", exc_info=e)
        return error_response(f"服务器错误", 500)


@git_notes_rest_bp.route("/get", methods=["POST"])
@authorship_notes_rest_bp.route("/get", methods=["POST"])
@auth_required
def get_note():
    """获取单个注释 (POST /worker/notes/get)

    请求:
    {
        "repo_url": "https://codeup.aliyun.com/org/repo.git",
        "commit_sha": "abc123def456..."
    }

    响应 (200):
    {
        "ok": true,
        "data": {
            "id": "ctg3h1e...",
            "commit_sha": "abc123def456...",
            "branch": "main",
            "author_name": "John Doe",
            "author_email": "john@example.com",
            "content": "<authorship log content>",
            "created_at": 1711670400000,
            "updated_at": 1711670400000
        }
    }

    响应 (404):
    {
        "ok": false,
        "error": "note not found"
    }
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return error_response("请求体不能为空", 400)

        if "repo_url" not in payload or "commit_sha" not in payload:
            return error_response("缺少必需字段: repo_url 和 commit_sha", 400)

        note = get_notes_service().get_note(
            repo_url=payload["repo_url"], commit_sha=payload["commit_sha"]
        )

        if not note:
            return error_response("note not found", 404)

        return ok_response(
            {
                "id": note.id,
                "commit_sha": note.commit_sha,
                "branch": note.branch,
                "author_name": note.author_name,
                "author_email": note.author_email,
                "content": note.note_content,
                "created_at": note.created_at,
                "updated_at": note.updated_at,
            }
        )

    except Exception as e:
        logger.error("获取单个注释错误", exc_info=e)
        return error_response(f"服务器错误", 500)


@git_notes_rest_bp.route("/batch", methods=["POST"])
@authorship_notes_rest_bp.route("/batch", methods=["POST"])
@auth_required
def batch_get_notes():
    """批量获取注释 (POST /worker/notes/batch)

    请求:
    {
        "repo_url": "https://codeup.aliyun.com/org/repo.git",
        "commit_shas": ["abc123...", "def456...", "789ghi..."]
    }

    响应 (200):
    {
        "ok": true,
        "data": {
            "notes": [
                {
                    "commit_sha": "abc123...",
                    "content": "<authorship log content>"
                },
                {
                    "commit_sha": "def456...",
                    "content": "<authorship log content>"
                }
            ],
            "missing": ["789ghi..."]
        }
    }
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return error_response("请求体不能为空", 400)

        if "repo_url" not in payload or "commit_shas" not in payload:
            return error_response("缺少必需字段: repo_url 和 commit_shas", 400)

        result = get_notes_service().batch_get_notes(
            repo_url=payload["repo_url"], commit_shas=payload["commit_shas"]
        )

        return ok_response(result)

    except Exception as e:
        logger.error("批量获取注释错误", exc_info=e)
        return error_response(f"服务器错误", 500)


@git_notes_rest_bp.route("/push", methods=["POST"])
@authorship_notes_rest_bp.route("/push", methods=["POST"])
@auth_required
def batch_push_notes():
    """批量推送（创建/更新）注释 (POST /worker/notes/push)

    请求:
    {
        "repo_url": "https://codeup.aliyun.com/org/repo.git",
        "notes": [
            {
                "branch": "main",
                "commit_sha": "abc123...",
                "commit_time": 1711670400,
                "note_blob_oid": "abc3434",
                "author_name": "John Doe",
                "author_email": "john@example.com",
                "content": "<authorship log content>"
            }
        ]
    }

    响应 (200):
    {
        "ok": true,
        "data": { "created": 3, "updated": 1 }
    }
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return error_response("请求体不能为空", 400)

        if "repo_url" not in payload or "notes" not in payload:
            return error_response("缺少必需字段: repo_url 和 notes", 400)

        result = get_notes_service().batch_push_notes(
            repo_url=payload["repo_url"], notes_data=payload["notes"]
        )

        return ok_response(result)

    except Exception as e:
        logger.error("批量推送（创建/更新）注释错误", exc_info=e)
        return error_response(f"服务器错误", 500)


@git_notes_rest_bp.route("/list", methods=["POST"])
@authorship_notes_rest_bp.route("/list", methods=["POST"])
@auth_required
def list_notes():
    """列出仓库中所有有注释的提交 SHA (POST /worker/notes/list)

    请求:
    {
        "repo_url": "https://codeup.aliyun.com/org/repo.git"
    }

    响应 (200):
    {
        "ok": true,
        "data": {
            "commit_shas": ["abc123...", "def456...", ...]
        }
    }
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return error_response("请求体不能为空", 400)

        if "repo_url" not in payload:
            return error_response("缺少必需字段: repo_url", 400)

        since_commit_time = payload.get("since_commit_time")
        commit_shas = get_notes_service().list_notes(
            repo_url=payload["repo_url"], since_commit_time=since_commit_time
        )

        return ok_response({"commit_shas": commit_shas})

    except Exception as e:
        logger.error("列出仓库中所有有注释的提交 SHA 错误", exc_info=e)
        return error_response(f"服务器错误", 500)


@git_notes_rest_bp.route("/search", methods=["POST"])
@authorship_notes_rest_bp.route("/search", methods=["POST"])
@auth_required
def search_notes():
    """在注释内容中搜索 (POST /worker/notes/search)

    请求:
    {
        "repo_url": "https://codeup.aliyun.com/org/repo.git",
        "pattern": "cursor"
    }

    响应 (200):
    {
        "ok": true,
        "data": {
            "commit_shas": ["abc123...", "def456..."]
        }
    }
    """
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return error_response("请求体不能为空", 400)

        if "repo_url" not in payload or "pattern" not in payload:
            return error_response("缺少必需字段: repo_url 和 pattern", 400)

        commit_shas = get_notes_service().search_notes(
            repo_url=payload["repo_url"], pattern=payload["pattern"]
        )

        return ok_response({"commit_shas": commit_shas})

    except Exception as e:
        logger.error("在注释内容中搜索错误", exc_info=e)
        return error_response(f"服务器错误", 500)
