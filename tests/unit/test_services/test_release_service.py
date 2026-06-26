from dataclasses import dataclass

import pytest

from core.services.release_service import ReleaseService, ReleaseValidationError


@dataclass
class UploadFile:
    filename: str
    data: bytes
    content_type: str = "application/octet-stream"

    def read(self):
        return self.data


class FakeReleaseDatabase:
    def __init__(self):
        self.created = None
        self.updated = None
        self.active_release = None
        self.artifacts = []

    def create_release(self, **kwargs):
        self.created = kwargs
        return {"id": "rel1", **{k: v for k, v in kwargs.items() if k != "artifacts"}}

    def update_release(self, release_id, **kwargs):
        self.updated = {"release_id": release_id, **kwargs}
        if release_id == "missing":
            return None
        return {"id": release_id, **{k: v for k, v in kwargs.items() if k != "artifacts"}}

    def get_active_release(self, channel):
        return self.active_release if channel == "latest" else None

    def list_artifacts(self, release_id):
        if self.active_release and release_id == self.active_release["id"]:
            return self.artifacts
        return []


def build_service():
    db = FakeReleaseDatabase()
    service = ReleaseService(
        database=db,
        config={
            "max_file_size_mb": 200,
            "max_files_per_release": 12,
            "allowed_channels": ["latest", "next"],
        },
    )
    return service, db


def test_create_release_generates_sha256sums_artifact():
    service, db = build_service()
    release = service.create_release(
        tag="v1.0.0",
        version="v1.0.0",
        channel="latest",
        description="test",
        created_by="tester",
        files=[
            UploadFile("install.ps1", b"ps"),
            UploadFile("git-ai-windows-x64.exe", b"exe"),
        ],
    )
    artifact_names = [a["filename"] for a in db.created["artifacts"]]
    assert release["id"] == "rel1"
    assert "SHA256SUMS" in artifact_names
    checksums = next(a for a in db.created["artifacts"] if a["filename"] == "SHA256SUMS")
    assert b"install.ps1" in checksums["content_blob"]
    assert db.created["sha256sums_checksum"] == checksums["sha256"]


def test_create_release_rejects_missing_windows_binary():
    service, _ = build_service()
    with pytest.raises(ReleaseValidationError, match="git-ai-windows-x64.exe"):
        service.create_release(
            tag="v1.0.0",
            version="v1.0.0",
            channel="latest",
            description=None,
            created_by=None,
            files=[
                UploadFile("install.ps1", b"ps"),
            ],
        )


def test_create_release_rejects_uploaded_sha256sums():
    service, _ = build_service()
    with pytest.raises(ReleaseValidationError, match="SHA256SUMS"):
        service.create_release(
            tag="v1.0.0",
            version="v1.0.0",
            channel="latest",
            description=None,
            created_by=None,
            files=[UploadFile("SHA256SUMS", b"bad")],
        )


def test_list_channel_metadata_returns_tag_version_and_platforms():
    service, db = build_service()
    db.active_release = {
        "id": "rel1",
        "tag": "v1.2.3",
        "version": "1.2.3",
        "sha256sums_checksum": "a" * 64,
    }
    db.artifacts = [
        {"filename": "install.ps1", "platform": "windows-x64"},
        {"filename": "git-ai-windows-x64.exe", "platform": "windows-x64"},
        {"filename": "SHA256SUMS", "platform": None},
    ]

    metadata = service.list_channel_metadata()

    assert metadata["latest"] == {
        "tag": "v1.2.3",
        "version": "1.2.3",
        "checksum": "a" * 64,
        "platforms": ["windows-x64"],
    }


def test_update_release_metadata_only_keeps_checksum():
    service, db = build_service()

    release = service.update_release(
        "rel1",
        tag=" v1.0.1 ",
        version="",
        channel="latest",
        description="new",
        files=[],
    )

    assert release["id"] == "rel1"
    assert db.updated["tag"] == "v1.0.1"
    assert db.updated["version"] == "v1.0.1"
    assert db.updated["channel"] == "latest"
    assert db.updated["description"] == "new"
    assert db.updated["artifacts"] is None
    assert db.updated["sha256sums_checksum"] is None


def test_update_release_with_files_regenerates_sha256sums():
    service, db = build_service()

    release = service.update_release(
        "rel1",
        tag="v1.0.1",
        version="1.0.1",
        channel="latest",
        description=None,
        files=[
            UploadFile("install.ps1", b"ps-new"),
            UploadFile("git-ai-windows-x64.exe", b"exe-new"),
        ],
    )

    assert release["id"] == "rel1"
    artifact_names = [artifact["filename"] for artifact in db.updated["artifacts"]]
    assert artifact_names == ["install.ps1", "git-ai-windows-x64.exe", "SHA256SUMS"]
    checksum_artifact = next(a for a in db.updated["artifacts"] if a["filename"] == "SHA256SUMS")
    assert db.updated["sha256sums_checksum"] == checksum_artifact["sha256"]
    assert b"install.ps1" in checksum_artifact["content_blob"]


def test_update_release_with_files_requires_windows_files():
    service, _ = build_service()

    with pytest.raises(ReleaseValidationError, match="git-ai-windows-x64.exe"):
        service.update_release(
            "rel1",
            tag="v1.0.1",
            version="1.0.1",
            channel="latest",
            description=None,
            files=[UploadFile("install.ps1", b"ps")],
        )


def test_update_release_rejects_uploaded_sha256sums():
    service, _ = build_service()

    with pytest.raises(ReleaseValidationError, match="SHA256SUMS"):
        service.update_release(
            "rel1",
            tag="v1.0.1",
            version="1.0.1",
            channel="latest",
            description=None,
            files=[UploadFile("SHA256SUMS", b"bad")],
        )
