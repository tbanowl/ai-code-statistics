from flask import Blueprint, request, jsonify
from core.config.logging import Logger
from api.schemas.cx_usage_schema import validate_batch, validate_event

cx_usage_bp = Blueprint("cx_usage", __name__, url_prefix="/api/v1/cx-aicode")
logger = Logger.get_logger("api.cx_usage")


@cx_usage_bp.route("/events/batch", methods=["POST"])
def events_batch():
    body = request.get_json(silent=True) or {}
    items = body.get("items", [])

    batch_result = validate_batch(items)
    if not batch_result["valid"]:
        return jsonify({"success": False, "error": batch_result["error"]}), batch_result["status_code"]

    valid_events, failed = [], []
    for i, item in enumerate(items):
        result = validate_event(item)
        if result["valid"]:
            valid_events.append(result["value"])
        else:
            event_id = item.get("eventId") if isinstance(item, dict) else None
            failed.append(str(event_id) if event_id else f"invalid:{i}")

    try:
        from core.database.cx_usage_db import CxUsageDatabase
        db = CxUsageDatabase()
        inserted = db.insert_batch(valid_events)
        all_failed = inserted["failed"] + failed
        return jsonify({
            "success": len(all_failed) == 0,
            "accepted": inserted["accepted"],
            "duplicated": inserted["duplicated"],
            "failed": all_failed,
        })
    except Exception as e:
        logger.error(f"cx_usage events/batch error: {e}", exc_info=True)
        all_failed = [ev["eventId"] for ev in valid_events] + failed
        return jsonify({
            "success": False,
            "error": "database unavailable",
            "accepted": [],
            "duplicated": [],
            "failed": all_failed,
        }), 503
