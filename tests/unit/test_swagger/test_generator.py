# tests/unit/test_swagger/test_generator.py
import pytest
from flask import Flask, Blueprint
from core.swagger.scanner import RouteInfo
from core.swagger.generator import to_swagger_format, generate_swagger_spec


def test_to_swagger_format_basic():
    """测试转换为 Swagger 2.0 格式"""
    route_info = RouteInfo(
        path='/test',
        methods={'GET'},
        function_name='test_endpoint',
        blueprint='api'
    )

    doc_data = {
        'path': '/test',
        'methods': ['GET'],
        'summary': 'Test endpoint',
        'description': 'A test endpoint'
    }

    swagger = to_swagger_format(route_info, doc_data)

    assert swagger['path'] == '/test'
    assert 'get' in swagger['operations']
    assert swagger['operations']['get']['summary'] == 'Test endpoint'
    assert swagger['operations']['get']['description'] == 'A test endpoint'


def test_generate_swagger_spec_template():
    """测试生成 Swagger 模板"""
    app = Flask(__name__)

    bp = Blueprint('test', __name__, url_prefix='/api')

    @bp.route('/items', methods=['GET'])
    def list_items():
        """
        List all items
        Returns a list of items
        """
        return []

    app.register_blueprint(bp)

    spec = generate_swagger_spec(
        app,
        docs_base_path='docs/api',
        api_config={
            'title': 'Test API',
            'version': '1.0.0',
            'description': 'A test API'
        }
    )

    assert spec['swagger'] == '2.0'
    assert spec['info']['title'] == 'Test API'
    assert spec['info']['version'] == '1.0.0'


def test_generate_swagger_spec_with_yaml_doc():
    """测试使用 YAML 文档生成 Swagger"""
    import tempfile
    import os

    app = Flask(__name__)

    bp = Blueprint('stats', __name__, url_prefix='/api/stats')

    @bp.route('/analyze', methods=['POST'])
    def analyze():
        return {}

    app.register_blueprint(bp)

    # 创建临时 YAML 文档
    yaml_content = """
tags:
  - name: stats
    description: Statistics API
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        spec = generate_swagger_spec(app, docs_base_path=temp_path.rsplit('\\', 1)[0])

        assert spec['swagger'] == '2.0'
        assert '/api/stats/analyze' in spec['paths']
    finally:
        os.unlink(temp_path)
