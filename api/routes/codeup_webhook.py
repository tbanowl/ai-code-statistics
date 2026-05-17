from flask import Blueprint, jsonify, request

from core.config.logging import Logger
from core.services.codeup_webhook_service import CodeupWebhookService, InvalidCodeupPayload

codeup_webhook_bp = Blueprint(
    "codeup_webhook", __name__, url_prefix="/webhook/codeup"
)
logger = Logger.get_logger("api.codeup_webhook")

service = CodeupWebhookService()


def get_codeup_webhook_service() -> CodeupWebhookService:
    return service


def success_response(data):
    return jsonify({"success": True, "data": data})


def error_response(message, status_code=400):
    return jsonify({"success": False, "error": message}), status_code


@codeup_webhook_bp.route("/merge", methods=["POST"])
def handle_merge_webhook():
    try:
        payload = request.get_json(silent=True)
        if not payload:
            return error_response("请求体不能为空", 400)

        result = get_codeup_webhook_service().enqueue_merge_event(payload)
        return success_response(result)

    except InvalidCodeupPayload as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error("处理 Codeup 合并 webhook 错误", exc_info=e)
        return error_response("服务器错误", 500)
