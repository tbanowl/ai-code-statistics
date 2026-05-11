from flask import Blueprint, jsonify, request

from core.config.logging import Logger

otel_receiver_bp = Blueprint("otel_receiver", __name__)
logger = Logger.get_logger("api.otel_receiver")


def _handle_logs_request():
    try:
        data = request.get_json(force=False, silent=False)
    except Exception as exc:
        return jsonify({"success": False, "error": f"Invalid JSON: {exc}"}), 400

    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid JSON: object payload required"}), 400

    try:
        from core.services.otel_logs_service import OtelLogsService

        result = OtelLogsService().process_logs(data)
        return jsonify(result), 200
    except Exception as exc:
        logger.error(f"OTLP logs receive error: {exc}", exc_info=True)
        return jsonify({"success": False, "error": str(exc)}), 500


@otel_receiver_bp.route("/v1/logs", methods=["POST"])
def receive_v1_logs():
    return _handle_logs_request()


@otel_receiver_bp.route("/worker/otel/v1/logs", methods=["POST"])
def receive_worker_otel_logs():
    return _handle_logs_request()
