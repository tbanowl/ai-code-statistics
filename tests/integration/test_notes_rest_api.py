"""
Comprehensive integration tests for Notes REST API
"""

import pytest
import json
import tempfile
import os
import sys
from typing import Any, cast
from sqlalchemy import create_engine

import core.config.loader as loader
import core.database.base as database_base
from core.database.base import Base, session_scope
from core.database.models import AuthorshipNotes
from core.services.notes_service import NotesRestService


@pytest.fixture
def app():
    """Create test app with temp database (module level)"""
    # 为每个测试调用创建新的临时数据库
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    temp_db_url = f'sqlite:///{path}'

    previous_config_data = loader.config_data
    previous_global_engine = database_base.global_engine
    previous_db_url = os.environ.get('DB_URL')
    sqlite_engine = create_engine(temp_db_url, echo=False)

    loader.config_data = {"database": {"url": temp_db_url, "echo": False}}
    database_base.global_engine = sqlite_engine
    Base.metadata.create_all(sqlite_engine)
    os.environ['DB_URL'] = temp_db_url

    # 需要在设置数据库后重新导入/刷新路由模块级 service
    import importlib
    if 'api.routes.authorship_notes' in sys.modules:
        authorship_notes = cast(
            Any, importlib.reload(sys.modules['api.routes.authorship_notes'])
        )
    else:
        authorship_notes = cast(
            Any, importlib.import_module('api.routes.authorship_notes')
        )
    authorship_notes.service = NotesRestService()

    from flask import Flask

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['DEBUG'] = True
    app.register_blueprint(authorship_notes.git_notes_rest_bp)
    app.register_blueprint(authorship_notes.authorship_notes_rest_bp)

    yield app

    # 清理
    authorship_notes.service.close()
    sqlite_engine.dispose()
    loader.config_data = previous_config_data
    database_base.global_engine = previous_global_engine
    if previous_db_url is None:
        os.environ.pop('DB_URL', None)
    else:
        os.environ['DB_URL'] = previous_db_url

    try:
        os.unlink(path)
    except (PermissionError, OSError):
        pass


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


def mark_note_superseded(commit_sha: str):
    from api.routes import authorship_notes

    with session_scope(authorship_notes.service.database.engine) as session:
        note = (
            session.query(AuthorshipNotes)
            .filter(AuthorshipNotes.commit_sha == commit_sha)
            .one()
        )
        note.status = "superseded"
        note.superseded_by = f"{commit_sha}-target"
        note.superseded_rewrite_id = f"rewrite-{commit_sha}"
        note.superseded_at = 1710000000000


def create_active_and_superseded_notes(client):
    for sha in ["active-sha", "superseded-sha"]:
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": sha,
                "original_commit_sha": None,
                "author_name": "Test",
                "author_email": "test@test.com",
                "content": f"content {sha}",
            },
            headers={'X-API-Key': 'test-key'}
        )
    mark_note_superseded("superseded-sha")


class TestCreateOrUpdateNote:
    """Tests for PUT /worker/notes"""

    def test_create_note_success(self, client):
        response = client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "abc123def4567890123456789012345678901234",
                "original_commit_sha": None,
                "author_name": "Test User",
                "author_email": "test@example.com",
                "content": "test content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert 'id' in data['data']
        assert len(data['data']['id']) == 20

    def test_update_note(self, client):
        # Create
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "abc123",
                "original_commit_sha": None,
                "author_name": "Test User",
                "author_email": "test@example.com",
                "content": "original content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        # Update
        response = client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "develop",
                "commit_sha": "abc123",
                "original_commit_sha": "xyz789",
                "author_name": "Updated User",
                "author_email": "updated@example.com",
                "content": "updated content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True

    def test_missing_required_field(self, client):
        response = client.put('/worker/notes',
            json={"repo_url": "https://test.com/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert '缺少必需字段' in data['error']

    def test_empty_request_body(self, client):
        response = client.put('/worker/notes',
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 400


class TestGetNote:
    """Tests for POST /worker/notes/get"""

    def test_get_note_success(self, client):
        # Create first
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "abc123",
                "original_commit_sha": None,
                "author_name": "Test User",
                "author_email": "test@example.com",
                "content": "test content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        # Get
        response = client.post('/worker/notes/get',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_sha": "abc123"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['data']['content'] == "test content"
        assert data['data']['author_name'] == "Test User"

    def test_get_note_not_found(self, client):
        response = client.post('/worker/notes/get',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_sha": "nonexistent"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['ok'] is False
        assert data['error'] == "note not found"


class TestBatchGetNotes:
    """Tests for POST /worker/notes/batch"""

    def test_batch_get_notes(self, client):
        # Create notes
        for sha in ["sha1", "sha2", "sha3"]:
            client.put('/worker/notes',
                json={
                    "repo_url": "https://github.com/test/repo.git",
                    "branch": "main",
                    "commit_sha": sha,
                    "original_commit_sha": None,
                    "author_name": "Test",
                    "author_email": "test@test.com",
                    "content": f"content {sha}"
                },
                headers={'X-API-Key': 'test-key'}
            )

        # Batch get
        response = client.post('/worker/notes/batch',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_shas": ["sha1", "sha2", "nonexistent"]
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert len(data['data']['notes']) == 2
        assert "nonexistent" in data['data']['missing']

    def test_batch_get_empty_list(self, client):
        response = client.post('/worker/notes/batch',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "commit_shas": []
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['notes'] == []
        assert data['data']['missing'] == []


class TestBatchPushNotes:
    """Tests for POST /worker/notes/push"""

    def test_batch_push_notes(self, client):
        response = client.post('/worker/notes/push',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "notes": [
                    {
                        "branch": "main",
                        "commit_sha": "sha1",
                        "original_commit_sha": None,
                        "author_name": "User1",
                        "author_email": "user1@test.com",
                        "content": "content1"
                    },
                    {
                        "branch": "main",
                        "commit_sha": "sha2",
                        "original_commit_sha": None,
                        "author_name": "User2",
                        "author_email": "user2@test.com",
                        "content": "content2"
                    }
                ]
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert data['data']['created'] == 2
        assert data['data']['updated'] == 0
        assert data['data']['unchanged'] == 0

    def test_batch_push_with_updates(self, client):
        # Create one note first
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "sha1",
                "original_commit_sha": None,
                "author_name": "User1",
                "author_email": "user1@test.com",
                "content": "old content"
            },
            headers={'X-API-Key': 'test-key'}
        )

        # Batch push including the existing one and a new one
        response = client.post('/worker/notes/push',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "notes": [
                    {
                        "branch": "main",
                        "commit_sha": "sha1",
                        "original_commit_sha": None,
                        "author_name": "User1 Updated",
                        "author_email": "user1@test.com",
                        "content": "new content"
                    },
                    {
                        "branch": "main",
                        "commit_sha": "sha2",
                        "original_commit_sha": None,
                        "author_name": "User2",
                        "author_email": "user2@test.com",
                        "content": "content2"
                    }
                ]
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['created'] == 1
        assert data['data']['updated'] == 1
        assert data['data']['unchanged'] == 0

    def test_batch_push_reports_unchanged_for_same_content(self, client):
        payload = {
            "repo_url": "https://github.com/test/repo.git",
            "notes": [
                {
                    "branch": "main",
                    "commit_sha": "sha1",
                    "original_commit_sha": None,
                    "author_name": "User1",
                    "author_email": "user1@test.com",
                    "content": "content1",
                }
            ]
        }

        client.post('/worker/notes/push', json=payload, headers={'X-API-Key': 'test-key'})
        response = client.post('/worker/notes/push', json=payload, headers={'X-API-Key': 'test-key'})

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data'] == {"created": 0, "updated": 0, "unchanged": 1}


class TestListNotes:
    """Tests for POST /worker/notes/list"""

    def test_list_notes(self, client):
        # Create notes
        for sha in ["sha1", "sha2", "sha3"]:
            client.put('/worker/notes',
                json={
                    "repo_url": "https://github.com/test/repo.git",
                    "branch": "main",
                    "commit_sha": sha,
                    "original_commit_sha": None,
                    "author_name": "Test",
                    "author_email": "test@test.com",
                    "content": "content"
                },
                headers={'X-API-Key': 'test-key'}
            )

        response = client.post('/worker/notes/list',
            json={"repo_url": "https://github.com/test/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert len(data['data']['commit_shas']) == 3
        assert set(data['data']['commit_shas']) == {"sha1", "sha2", "sha3"}

    def test_list_notes_empty(self, client):
        response = client.post('/worker/notes/list',
            json={"repo_url": "https://github.com/empty/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['commit_shas'] == []

    def test_list_notes_rejects_invalid_incremental_params(self, client):
        response = client.post('/worker/notes/list',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "since_change_seq": "bad",
                "limit": "also-bad",
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert "since_change_seq" in data['error']

    def test_list_notes_returns_incremental_summary_fields(self, client):
        for sha, content in [("sha1", "content one"), ("sha2", "content two")]:
            client.put('/worker/notes',
                json={
                    "repo_url": "https://github.com/test/repo.git",
                    "branch": "main",
                    "commit_sha": sha,
                    "original_commit_sha": None,
                    "author_name": "Test",
                    "author_email": "test@test.com",
                    "content": content,
                },
                headers={'X-API-Key': 'test-key'}
            )

        response = client.post('/worker/notes/list',
            json={"repo_url": "https://github.com/test/repo.git", "since_change_seq": 0, "limit": 1},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert len(data['data']['commit_shas']) == 1
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['commit_sha'] == 'sha1'
        assert data['data']['items'][0]['content_hash'].startswith('sha256:')
        assert data['data']['items'][0]['change_seq'] > 0
        assert data['data']['next_change_seq'] == data['data']['items'][0]['change_seq']
        assert data['data']['has_more'] is True

    def test_notes_list_filters_superseded_by_default_and_reads_query_flag(self, client):
        create_active_and_superseded_notes(client)

        default_response = client.post('/worker/notes/list',
            json={"repo_url": "https://github.com/test/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )
        audit_response = client.post('/worker/notes/list?include_superseded=true',
            json={"repo_url": "https://github.com/test/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )

        assert default_response.status_code == 200
        default_data = json.loads(default_response.data)
        assert default_data['data']['commit_shas'] == ["active-sha"]

        assert audit_response.status_code == 200
        audit_data = json.loads(audit_response.data)
        assert set(audit_data['data']['commit_shas']) == {
            "active-sha",
            "superseded-sha",
        }

    def test_authorship_notes_list_filters_superseded_by_default_and_reads_query_flag(self, client):
        create_active_and_superseded_notes(client)

        default_response = client.post('/worker/authorship_notes/list',
            json={"repo_url": "https://github.com/test/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )
        audit_response = client.post('/worker/authorship_notes/list?include_superseded=true',
            json={"repo_url": "https://github.com/test/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )

        assert default_response.status_code == 200
        default_data = json.loads(default_response.data)
        assert default_data['data']['commit_shas'] == ["active-sha"]

        assert audit_response.status_code == 200
        audit_data = json.loads(audit_response.data)
        assert set(audit_data['data']['commit_shas']) == {
            "active-sha",
            "superseded-sha",
        }

    def test_list_notes_rejects_invalid_include_superseded_query_param(self, client):
        response = client.post('/worker/notes/list?include_superseded=maybe',
            json={"repo_url": "https://github.com/test/repo.git"},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['ok'] is False
        assert "include_superseded" in data['error']

    def test_batch_get_returns_hash_and_change_seq(self, client):
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "sha1",
                "original_commit_sha": None,
                "author_name": "Test",
                "author_email": "test@test.com",
                "content": "content one",
            },
            headers={'X-API-Key': 'test-key'}
        )

        response = client.post('/worker/notes/batch',
            json={"repo_url": "https://github.com/test/repo.git", "commit_shas": ["sha1"]},
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        note = data['data']['notes'][0]
        assert note['commit_sha'] == 'sha1'
        assert note['content_hash'].startswith('sha256:')
        assert note['change_seq'] > 0


class TestSearchNotes:
    """Tests for POST /worker/notes/search"""

    def test_search_notes(self, client):
        # Create notes
        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "sha1",
                "original_commit_sha": None,
                "author_name": "Test",
                "author_email": "test@test.com",
                "content": "cursor position"
            },
            headers={'X-API-Key': 'test-key'}
        )

        client.put('/worker/notes',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "branch": "main",
                "commit_sha": "sha2",
                "original_commit_sha": None,
                "author_name": "Test",
                "author_email": "test@test.com",
                "content": "buffer size"
            },
            headers={'X-API-Key': 'test-key'}
        )

        response = client.post('/worker/notes/search',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "pattern": "cursor"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ok'] is True
        assert "sha1" in data['data']['commit_shas']

    def test_search_notes_no_results(self, client):
        response = client.post('/worker/notes/search',
            json={
                "repo_url": "https://github.com/test/repo.git",
                "pattern": "nonexistent"
            },
            headers={'X-API-Key': 'test-key'}
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['data']['commit_shas'] == []
