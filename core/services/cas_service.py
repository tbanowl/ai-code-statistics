"""CAS (Content Addressable Storage) 服务"""
import json
from typing import List, Dict
from core.config.logging import Logger


class CasService:
    """CAS (Content Addressable Storage) 服务"""

    def __init__(self):
        self.logger = Logger.get_logger('services.cas')
        from core.database.metrics_db import MetricsDatabase
        from core.config import load_config
        self.database = MetricsDatabase()

        from core.config import load_config
        cas_config = load_config().get('git_ai', {}).get('cas', {})
        self.max_objects = cas_config.get('max_objects_per_request', 100)

    def upload_objects(self, objects: List[Dict]) -> Dict:
        """
        上传 CAS 对象

        请求格式:
        {
            "objects": [
                {
                    "content": {...},
                    "hash": "string",
                    "metadata": {...}
                },
                ...
            ]
        }

        响应格式:
        {
            "results": [{"hash": "...", "status": "ok", "error": null}],
            "success_count": 1,
            "failure_count": 0
        }
        """
        if len(objects) > self.max_objects:
            return {
                'error': f'Too many objects, maximum {self.max_objects} allowed',
                'results': [],
                'success_count': 0,
                'failure_count': 0
            }

        results = []
        success_count = 0
        failure_count = 0

        for obj in objects:
            obj_hash = obj.get('hash', "")
            content = obj.get('content')
            metadata = obj.get('metadata')

            try:
                self.database.save_cas_object(
                    hash=obj_hash,
                    content_json=content,
                    metadata_json=metadata
                )
                results.append({
                    'hash': obj_hash,
                    'status': 'ok',
                    'error': None
                })
                success_count += 1
            except Exception as e:
                self.logger.error(f"保存 CAS 对象失败: {e}")
                results.append({
                    'hash': obj_hash,
                    'status': 'error',
                    'error': str(e)
                })
                failure_count += 1

        return {
            'results': results,
            'success_count': success_count,
            'failure_count': failure_count
        }

    def read_objects(self, hashes: List[str]) -> Dict:
        """
        读取 CAS 对象

        请求格式: hashes=hash1,hash2,hash3

        响应格式:
        {
            "results": [
                {
                    "hash": "hash1",
                    "status": "ok",
                    "content": {...},
                    "error": None
                }
            ],
            "success_count": 1,
            "failure_count": 0
        }
        """
        results = []
        success_count = 0
        failure_count = 0

        for obj_hash in hashes:
            obj = self.database.get_cas_object(obj_hash)

            if obj:
                try:
                    content = obj.get('content_json')
                    results.append({
                        'hash': obj_hash,
                        'status': 'ok',
                        'content': content,
                        'error': None
                    })
                    success_count += 1
                except Exception as e:
                    self.logger.error(f"解析 CAS 对象内容失败: {e}")
                    results.append({
                        'hash': obj_hash,
                        'status': 'error',
                        'content': None,
                        'error': str(e)
                    })
                    failure_count += 1
            else:
                results.append({
                    'hash': obj_hash,
                    'status': 'error',
                    'content': None,
                    'error': 'Not found'
                })
                failure_count += 1

        return {
            'results': results,
            'success_count': success_count,
            'failure_count': failure_count
        }
