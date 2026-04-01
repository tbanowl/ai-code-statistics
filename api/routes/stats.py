import logging

from flask import Blueprint, current_app, jsonify, request

from core.database import BlameStatsDatabase, StatsDatabase

stats_bp = Blueprint("stats", __name__, url_prefix="/api/stats")


def _get_pagination() -> tuple[int, int]:
    page = request.args.get("page", type=int)
    page_size = request.args.get("page_size", type=int)
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", type=int)

    if page is not None or page_size is not None:
        page = page or 1
        page_size = page_size or 20
    elif limit is not None or offset is not None:
        limit = limit or 20
        offset = offset or 0
        page_size = max(1, limit)
        page = offset // page_size + 1
    else:
        page = 1
        page_size = 20

    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise ValueError("page_size must be between 1 and 100")

    return page, page_size


def _build_summary(items: list[dict]) -> dict:
    def _to_int(value: object) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            return int(value) if value.isdigit() else 0
        return 0

    total_generated = sum(_to_int(i.get("ai_generated_lines")) for i in items)
    total_accepted = sum(_to_int(i.get("ai_accepted_lines")) for i in items)
    total_human = sum(_to_int(i.get("human_lines")) for i in items)
    total = total_accepted + total_human
    avg_pct = round((total_accepted / total) * 100, 2) if total > 0 else 0

    return {
        "total_ai_generated": total_generated,
        "total_ai_accepted": total_accepted,
        "total_human": total_human,
        "avg_ai_percentage": avg_pct,
    }


def _get_stats_repo_databases() -> tuple[StatsDatabase, BlameStatsDatabase]:
    return StatsDatabase(), BlameStatsDatabase()


def _get_ssh_key_service():
    from core.services import SshKeyService

    return SshKeyService()


@stats_bp.route("/repositories", methods=["GET"])
def get_repositories():
    try:
        page, page_size = _get_pagination()
        keyword = request.args.get("keyword")

        db = StatsDatabase()
        result = db.get_repositories(page=page, page_size=page_size, keyword=keyword)
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
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@stats_bp.route("/repositories/consolidation-report", methods=["GET"])
def get_repository_consolidation_report():
    try:
        db = StatsDatabase()
        report = db.get_repository_consolidation_report()
        return jsonify({"success": True, "data": report})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@stats_bp.route("/stats/contributors", methods=["GET"])
def get_contributors():
    try:
        page, page_size = _get_pagination()
        keyword = request.args.get("keyword")

        db = StatsDatabase()
        result = db.get_contributors(page=page, page_size=page_size, keyword=keyword)
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
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@stats_bp.route("/", methods=["GET"])
def get_stats():
    try:
        start_date = request.args.get("start_date", type=int)
        end_date = request.args.get("end_date", type=int)
        if start_date is None or end_date is None:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "start_date and end_date are required",
                    }
                ),
                400,
            )

        granularity = request.args.get("granularity", "daily")
        if granularity not in ("daily", "weekly", "monthly"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "granularity must be daily, weekly, or monthly",
                    }
                ),
                400,
            )

        db = StatsDatabase()
        repo_id = request.args.get("repo_id")
        contributor_id = request.args.get("contributor_id")
        items = db.get_aggregated_stats(
            start_date=start_date,
            end_date=end_date,
            repo_id=repo_id,
            contributor_id=contributor_id,
            granularity=granularity,
        )

        filters = {
            "repo_id": repo_id,
            "repo_name": None,
            "contributor_id": contributor_id,
            "contributor_name": None,
        }
        if repo_id:
            repo = db.get_repository_by_id(repo_id)
            if repo:
                filters["repo_name"] = repo.get("repo_name")
        if contributor_id:
            contributor = db.get_contributor_by_id(contributor_id)
            if contributor:
                filters["contributor_name"] = contributor.get("name")

        return jsonify(
            {
                "success": True,
                "data": {
                    "items": items,
                    "summary": _build_summary(items),
                    "filters": filters,
                },
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@stats_bp.route("/daily", methods=["GET"])
def get_daily_stats():
    try:
        page, page_size = _get_pagination()

        db = StatsDatabase()
        result = db.get_daily_stats_paginated(
            page=page,
            page_size=page_size,
            start_date=request.args.get("start_date", type=int),
            end_date=request.args.get("end_date", type=int),
            repo_id=request.args.get("repo_id"),
            contributor_id=request.args.get("contributor_id"),
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
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@stats_bp.route("/aggregate", methods=["GET"])
def get_stats_aggregate_compat():
    try:
        start_date = request.args.get("start_date", type=int)
        end_date = request.args.get("end_date", type=int)
        if start_date is None or end_date is None:
            return jsonify(
                {"success": False, "error": "start_date and end_date are required"}
            ), 400

        db = StatsDatabase()
        repo_id = request.args.get("repo_id")
        contributor_id = request.args.get("contributor_id")

        items = db.get_aggregated_stats(
            start_date=start_date,
            end_date=end_date,
            repo_id=repo_id,
            contributor_id=contributor_id,
            granularity="daily",
        )
        detail_rows = db.query_daily_stats(
            start_date=start_date,
            end_date=end_date,
            repo_id=repo_id,
            contributor_id=contributor_id,
            limit=100000,
            offset=0,
        )

        repo_url = None
        contributor_uid = None
        if repo_id:
            repo = db.get_repository_by_id(repo_id)
            if repo:
                repo_url = repo.get("repo_path")
        if contributor_id:
            contributor = db.get_contributor_by_id(contributor_id)
            if contributor:
                contributor_uid = contributor.get("contributor_uid")

        committed_rows = db.query_committed_events(
            start_ts=start_date,
            end_ts=end_date,
            repo_url=repo_url,
            author=contributor_uid,
        )

        summary = _build_summary(items)
        total_commits = len(committed_rows)
        ai_commits = sum(
            1 for row in committed_rows if int(row.get("ai_accepted_lines") or 0) > 0
        )
        return jsonify(
            {
                "total_commits": total_commits,
                "ai_commits": ai_commits,
                "ai_commit_pct": round((ai_commits / total_commits) * 100, 2)
                if total_commits > 0
                else 0,
                "total_lines": summary["total_ai_accepted"] + summary["total_human"],
                "ai_lines": summary["total_ai_accepted"],
                "ai_lines_pct": summary["avg_ai_percentage"],
            }
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@stats_bp.route("/stats/aggregate", methods=["POST"])
def trigger_aggregate():
    scheduler = current_app.config.get("_scheduler")
    if scheduler is None:
        return jsonify({"success": False, "error": "scheduler is not enabled"}), 503

    payload = request.get_json(silent=True) or {}
    context = {}

    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    if start_date is not None:
        context["start_date"] = int(start_date)
    if end_date is not None:
        context["end_date"] = int(end_date)

    repo_id = payload.get("repo_id")
    contributor_id = payload.get("contributor_id")

    db = StatsDatabase()
    if repo_id:
        repo = db.get_repository_by_id(str(repo_id))
        if not repo:
            return jsonify({"success": False, "error": "repo_id not found"}), 404
        context["repo_url"] = repo.get("repo_path")
    if contributor_id:
        contributor = db.get_contributor_by_id(str(contributor_id))
        if not contributor:
            return jsonify({"success": False, "error": "contributor_id not found"}), 404
        context["contributor"] = contributor.get("contributor_uid") or contributor.get(
            "name"
        )

    execution_id = scheduler.trigger_job_with_execution("daily_aggregation", context)
    if execution_id is None:
        running = scheduler.scheduler_db.get_running_task_execution("daily_aggregation")
        if running:
            return (
                jsonify({"success": False, "error": "daily_aggregation is running"}),
                409,
            )
        return jsonify(
            {"success": False, "error": "failed to trigger aggregation"}
        ), 500

    return jsonify(
        {
            "success": True,
            "data": {
                "execution_id": execution_id,
                "status": "pending",
                "message": "aggregation submitted",
            },
        }
    )
