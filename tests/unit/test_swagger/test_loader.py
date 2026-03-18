# tests/unit/test_swagger/test_loader.py
import pytest
import tempfile
import os
from core.swagger.loader import load_blueprint_doc, merge_with_route
from core.swagger.scanner import RouteInfo


def test_load_blueprint_doc_success():
    """测试成功加载 Blueprint 文档"""
    yaml_content = """
tags:
  - name: stats
    description: 统计分析 API

endpoints:
  /analyze:
    POST:
      summary: 执行统计分析
      description: 根据日期范围统计分析
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        doc = load_blueprint_doc(temp_path)

        assert len(doc['tags']) == 1
        assert doc['tags'][0]['name'] == 'stats'
        assert '/analyze' in doc['endpoints']
    finally:
        os.unlink(temp_path)


def test_load_blueprint_doc_not_found():
    """测试文件不存在的处理"""
    doc = load_blueprint_doc('non_existent_file.yaml')

    assert doc is None


def test_merge_with_route():
    """测试路由信息与文档合并"""
    route_info = RouteInfo(
        path='/analyze',
        methods={'POST'},
        function_name='analyze',
        blueprint='stats',
        parameters=[],
        docstring='Original docstring'
    )

    doc_data = {
        'tags': [{'name': 'stats', 'description': '统计分析 API'}],
        'endpoints': {
            '/analyze': {
                'POST': {
                    'summary': '执行统计分析',
                    'description': '根据日期范围统计分析'
                }
            }
        }
    }

    merged = merge_with_route(route_info, doc_data)

    assert merged['path'] == '/analyze'
    assert merged['methods'] == ['POST']
    assert merged['summary'] == '执行统计分析'
    assert merged['description'] == '根据日期范围统计分析'


def test_merge_with_route_no_docstring():
    """测试没有文档时的合并（使用 docstring）"""
    route_info = RouteInfo(
        path='/test',
        methods={'GET'},
        function_name='test_endpoint',
        blueprint='api',
        parameters=[],
        docstring='A test endpoint for testing'
    )

    doc_data = {
        'endpoints': {}
    }

    merged = merge_with_route(route_info, doc_data)

    assert merged['path'] == '/test'
    assert merged['summary'] == 'A test endpoint for testing'
