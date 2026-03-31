from unittest.mock import MagicMock, patch

from core.services.cas_service import CasService


def _build_service(max_objects=100):
    with patch(
        "core.config.load_config",
        return_value={"git_ai": {"cas": {"max_objects_per_request": max_objects}}},
    ):
        with patch("core.database.metrics_db.MetricsDatabase") as db_cls:
            db = MagicMock()
            db_cls.return_value = db
            service = CasService()
    return service, db


def test_upload_objects_success():
    service, db = _build_service()
    result = service.upload_objects(
        [{"hash": "abc", "content": {"k": 1}, "metadata": {"m": 2}}]
    )
    assert result["success_count"] == 1
    assert result["failure_count"] == 0
    db.save_cas_object.assert_called_once_with(
        hash="abc", content_json={"k": 1}, metadata_json={"m": 2}
    )


def test_upload_objects_respects_limit():
    service, db = _build_service(max_objects=1)
    result = service.upload_objects(
        [
            {"hash": "a", "content": {}},
            {"hash": "b", "content": {}},
        ]
    )
    assert "error" in result
    assert result["success_count"] == 0
    db.save_cas_object.assert_not_called()


def test_upload_objects_handles_db_error():
    service, db = _build_service()
    db.save_cas_object.side_effect = Exception("db down")
    result = service.upload_objects([{"hash": "abc", "content": {}}])
    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert result["results"][0]["status"] == "error"


def test_read_objects_success_and_missing():
    service, db = _build_service()
    db.get_cas_object.side_effect = [
        {"hash": "abc", "content_json": {"x": 1}},
        None,
    ]
    result = service.read_objects(["abc", "missing"])
    assert result["success_count"] == 1
    assert result["failure_count"] == 1
    assert result["results"][0]["content"] == {"x": 1}
    assert result["results"][1]["error"] == "Not found"
