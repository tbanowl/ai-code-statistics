"""
Comprehensive integration tests for Notes REST API
"""

import pytest
import json
import tempfile
import os
import sys


@pytest.fixture
def app():
    """Create test app with temp database (module level)"""
    # 为每个测试调用创建新的临时数据库
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    temp_db_url = f'sqlite:///{path}'

    os.environ['DB_URL'] = temp_db_url

    # 需要在设置环境变量后重新导入模块
    import importlib
    if 'api.routes.notes_rest' in sys.modules:
        importlib.reload(sys.modules['api.routes.notes_rest'])

    from api.routes.authorship_notes import git_notes_rest_bp
    from flask import Flask

    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['DEBUG'] = True
    app.register_blueprint(git_notes_rest_bp)

    # 关闭引擎以允许删除文件
    from core.services.notes_service import NotesRestService

    yield app

    # 清理
    service = NotesRestService()
    service.close()

    try:
        os.unlink(path)
    except (PermissionError, OSError):
        pass


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


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
