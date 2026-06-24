from typing import Any

from sqlalchemy.exc import IntegrityError

from .base import BaseDatabase, now_ts, session_scope
from .models import GitAiRelease, GitAiReleaseArtifact


class ReleaseDatabase(BaseDatabase):
    def _release_dict(self, release: GitAiRelease) -> dict[str, Any]:
        data = release.to_dict()
        data.pop("active_channel", None)
        return data

    def create_release(
        self,
        *,
        tag: str,
        version: str,
        channel: str,
        sha256sums_checksum: str,
        artifacts: list[dict[str, Any]],
        description: str | None,
        created_by: str | None,
    ) -> dict[str, Any]:
        with session_scope(self.engine) as session:
            release = GitAiRelease(
                tag=tag,
                version=version,
                channel=channel,
                status="inactive",
                sha256sums_checksum=sha256sums_checksum,
                description=description,
                created_by=created_by,
                published_at=None,
            )
            session.add(release)
            session.flush()
            for artifact in artifacts:
                session.add(GitAiReleaseArtifact(release_id=release.id, **artifact))
            session.flush()
            return self._release_dict(release)

    def activate_release(self, release_id: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            release = (
                session.query(GitAiRelease)
                .filter(GitAiRelease.id == release_id)
                .first()
            )
            if release is None:
                return None
            session.query(GitAiRelease).filter(
                GitAiRelease.channel == release.channel
            ).with_for_update().all()
            session.query(GitAiRelease).filter(
                GitAiRelease.channel == release.channel,
                GitAiRelease.status == "active",
            ).update({"status": "inactive", "updated_at": now_ts()})
            release.status = "active"
            release.published_at = now_ts()
            release.updated_at = now_ts()
            try:
                session.flush()
            except IntegrityError as exc:
                raise ValueError("another release is already active for this channel") from exc
            return self._release_dict(release)

    def get_release(self, release_id: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            release = (
                session.query(GitAiRelease)
                .filter(GitAiRelease.id == release_id)
                .first()
            )
            return self._release_dict(release) if release else None

    def get_active_release(self, channel: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            release = (
                session.query(GitAiRelease)
                .filter(
                    GitAiRelease.channel == channel,
                    GitAiRelease.status == "active",
                )
                .first()
            )
            return self._release_dict(release) if release else None

    def list_releases(
        self, channel: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        with session_scope(self.engine) as session:
            query = session.query(GitAiRelease)
            if channel:
                query = query.filter(GitAiRelease.channel == channel)
            if status:
                query = query.filter(GitAiRelease.status == status)
            rows = query.order_by(GitAiRelease.created_at.desc()).all()
            return [self._release_dict(row) for row in rows]

    def list_artifacts(
        self, release_id: str, include_content: bool = False
    ) -> list[dict[str, Any]]:
        with session_scope(self.engine) as session:
            rows = (
                session.query(GitAiReleaseArtifact)
                .filter(GitAiReleaseArtifact.release_id == release_id)
                .order_by(GitAiReleaseArtifact.filename.asc())
                .all()
            )
            result = []
            for row in rows:
                data = row.to_dict()
                if not include_content:
                    data.pop("content_blob", None)
                result.append(data)
            return result

    def get_artifact(self, release_id: str, filename: str) -> dict[str, Any] | None:
        with session_scope(self.engine) as session:
            row = (
                session.query(GitAiReleaseArtifact)
                .filter(
                    GitAiReleaseArtifact.release_id == release_id,
                    GitAiReleaseArtifact.filename == filename,
                )
                .first()
            )
            return row.to_dict() if row else None

    def delete_release(self, release_id: str) -> bool:
        with session_scope(self.engine) as session:
            release = (
                session.query(GitAiRelease)
                .filter(GitAiRelease.id == release_id)
                .first()
            )
            if release is None or release.status == "active":
                return False
            session.delete(release)
            return True
