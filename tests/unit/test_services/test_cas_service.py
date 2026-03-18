"""测试 CasService"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.services.cas_service import CasService


class TestCasService:
    """测试 CasService"""

    def test_upload_single_object_success(self):
        """成功上传单个 CAS 对象"""
        mock_db = Mock()
        mock_db.save_cas_object.return_value = None

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {}
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()

            objects = [{
                'hash': 'abc123',
                'content': {'data': 'test'},
                'metadata': {'type': 'file'}
            }]

            result = service.upload_objects(objects)

            assert result['success_count'] == 1
            assert result['failure_count'] == 0
            assert len(result['results']) == 1
            assert result['results'][0]['hash'] == 'abc123'
            assert result['results'][0]['status'] == 'ok'
            assert result['results'][0]['error'] is None

            mock_db.save_cas_object.assert_called_once_with(
                hash='abc123',
                content_json='{"data": "test"}',
                metadata_json='{"type": "file"}'
            )

    def test_upload_multiple_objects_success(self):
        """成功上传多个 CAS 对象"""
        mock_db = Mock()
        mock_db.save_cas_object.return_value = None

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {}
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()

            objects = [
                {'hash': 'abc123', 'content': {'data': 'test1'}},
                {'hash': 'def456', 'content': {'data': 'test2'}},
                {'hash': 'ghi789', 'content': {'data': 'test3'}}
            ]

            result = service.upload_objects(objects)

            assert result['success_count'] == 3
            assert result['failure_count'] == 0
            assert len(result['results']) == 3

    def test_upload_empty_objects(self):
        """上传空对象列表"""
        mock_db = Mock()

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {}
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()

            result = service.upload_objects([])

            assert result['success_count'] == 0
            assert result['failure_count'] == 0
            assert len(result['results']) == 0

            mock_db.save_cas_object.assert_not_called()

    def test_upload_handles_database_error(self):
        """处理数据库错误"""
        mock_db = Mock()
        mock_db.save_cas_object.side_effect = Exception("Database connection failed")

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {}
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db
            mock_logger = MagicMock()
            service = CasService()
            service.logger = mock_logger

            objects = [{'hash': 'abc123', 'content': {'data': 'test'}}]

            result = service.upload_objects(objects)

            assert result['success_count'] == 0
            assert result['failure_count'] == 1
            assert result['results'][0]['status'] == 'error'
            assert "Database connection failed" in result['results'][0]['error']

    def test_upload_exceeds_max_objects(self):
        """超过最大对象数量限制"""
        mock_db = Mock()

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            # 正确设置链式调用: ConfigLoader().load().get('git_ai', {}).get('cas', {})
            mock_load_result = Mock()
            mock_git_ai_result = Mock()
            mock_cas_result = {'max_objects_per_request': 2}
            mock_git_ai_result.get.return_value = mock_cas_result
            mock_load_result.get.return_value = mock_git_ai_result
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()

            objects = [
                {'hash': 'abc123', 'content': {}},
                {'hash': 'def456', 'content': {}},
                {'hash': 'ghi789', 'content': {}}
            ]

            result = service.upload_objects(objects)

            assert 'error' in result
            assert 'Too many objects' in result['error']
            assert 'maximum 2 allowed' in result['error']
            assert result['success_count'] == 0
            assert result['failure_count'] == 0

            mock_db.save_cas_object.assert_not_called()

    def test_read_single_object_success(self):
        """成功读取单个 CAS 对象"""
        mock_db = Mock()
        mock_db.get_cas_object.return_value = {
            'hash': 'abc123',
            'content_json': '{"data": "test"}',
            'metadata_json': '{"type": "file"}'
        }

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {}
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()

            result = service.read_objects(['abc123'])

            assert result['success_count'] == 1
            assert result['failure_count'] == 0
            assert len(result['results']) == 1
            assert result['results'][0]['hash'] == 'abc123'
            assert result['results'][0]['status'] == 'ok'
            assert result['results'][0]['content'] == {'data': 'test'}
            assert result['results'][0]['error'] is None

            mock_db.get_cas_object.assert_called_once_with('abc123')

    def test_read_multiple_objects_success(self):
        """成功读取多个 CAS 对象"""
        mock_db = Mock()

        def get_side_effect(hash_val):
            mapping = {
                'abc123': {'hash': 'abc123', 'content_json': '{"data": "test1"}'},
                'def456': {'hash': 'def456', 'content_json': '{"data": "test2"}'},
                'ghi789': {'hash': 'ghi789', 'content_json': '{"data": "test3"}'}
            }
            return mapping.get(hash_val)

        mock_db.get_cas_object.side_effect = get_side_effect

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {}
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()

            result = service.read_objects(['abc123', 'def456', 'ghi789'])

            assert result['success_count'] == 3
            assert result['failure_count'] == 0

    def test_read_empty_hashes(self):
        """读取空哈希列表"""
        mock_db = Mock()

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {}
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()

            result = service.read_objects([])

            assert result['success_count'] == 0
            assert result['failure_count'] == 0
            assert len(result['results']) == 0

            mock_db.get_cas_object.assert_not_called()

    def test_read_object_not_found(self):
        """对象不存在"""
        mock_db = Mock()
        mock_db.get_cas_object.return_value = None

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {}
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()

            result = service.read_objects(['nonexistent'])

            assert result['success_count'] == 0
            assert result['failure_count'] == 1
            assert result['results'][0]['error'] == 'Not found'
            assert result['results'][0]['content'] is None

    def test_read_partial_success(self):
        """部分成功读取"""
        mock_db = Mock()

        def get_side_effect(hash_val):
            if hash_val == 'abc123':
                return {'hash': 'abc123', 'content_json': '{"data": "test"}'}
            return None

        mock_db.get_cas_object.side_effect = get_side_effect

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {}
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()

            result = service.read_objects(['abc123', 'nonexistent'])

            assert result['success_count'] == 1
            assert result['failure_count'] == 1
            assert result['results'][0]['status'] == 'ok'
            assert result['results'][1]['status'] == 'error'

    def test_custom_max_objects_limit(self):
        """自定义最大对象数量限制"""
        mock_db = Mock()
        mock_db.save_cas_object.return_value = None

        with patch('core.config.ConfigLoader') as mock_config_loader, \
             patch('core.database.factory.create_database') as mock_create_db:
            mock_load_result = Mock()
            mock_load_result.get.return_value = {
                'max_objects_per_request': 50
            }
            mock_config_loader.return_value.load.return_value = mock_load_result
            mock_create_db.return_value = mock_db

            service = CasService()
            # 创建 50 个对象
            objects = [{'hash': f'hash{i}', 'content': {}} for i in range(50)]

            result = service.upload_objects(objects)

            assert result['success_count'] == 50
            assert 'error' not in result

            # 测试 51 个对象
            objects.append({'hash': 'hash50', 'content': {}})
            result = service.upload_objects(objects)

            assert 'error' in result
            assert 'maximum 50 allowed' in result['error']
