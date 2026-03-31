"""
Swagger 文档生成器 - 合并扫描结果和 YAML 生成 Swagger 配置
"""
from flask import Flask
from typing import Dict, Any
from core.swagger.scanner import scan_routes
from core.swagger.loader import load_blueprint_doc, merge_with_route


def to_swagger_format(route_info, merged_doc: Dict[str, Any]) -> Dict[str, Any]:
    """转换为 Swagger 2.0 格式"""
    path_item = {'path': route_info.path, 'operations': {}}

    for method in route_info.methods:
        method_lower = method.lower()

        operation = {
            'summary': merged_doc.get('summary', route_info.function_name),
            'description': merged_doc.get('description', ''),
            'tags': [route_info.blueprint] if route_info.blueprint else []
        }

        if 'parameters' in merged_doc:
            operation['parameters'] = merged_doc['parameters']

        if 'responses' in merged_doc:
            operation['responses'] = merged_doc['responses']

        path_item['operations'][method_lower] = operation

    return path_item


def generate_swagger_spec(
    app: Flask,
    docs_base_path: str,
    api_config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """生成完整的 Swagger 规范"""
    if api_config is None:
        api_config = {}

    routes = scan_routes(app)

    paths = {}
    for route in routes:
        doc_path = f"{docs_base_path}/{route.blueprint}.yaml" if route.blueprint else None
        print(f'doc path: {doc_path}')
        doc_data = load_blueprint_doc(doc_path) if doc_path else {}
        if doc_data is None:
            doc_data = {}

        merged = merge_with_route(route, doc_data)
        swagger_item = to_swagger_format(route, merged)

        path_obj = {}
        for method, op in swagger_item['operations'].items():
            path_obj[method] = op

        if path_obj:
            paths[route.path] = path_obj

    spec = {
        'swagger': '2.0',
        'info': {
            'title': api_config.get('title', 'API Documentation'),
            'version': api_config.get('version', '1.0.0'),
            'description': api_config.get('description', '')
        },
        'basePath': '/',
        'schemes': ['http', 'https'],
        'consumes': ['application/json'],
        'produces': ['application/json'],
        'paths': paths,
        'definitions': _get_common_definitions()
    }

    tags = _extract_tags(routes, docs_base_path)
    if tags:
        spec['tags'] = tags

    return spec


def _get_common_definitions() -> Dict[str, Any]:
    """获取通用响应定义"""
    return {
        'SuccessResponse': {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean', 'example': True},
                'data': {'type': 'object'}
            }
        },
        'ErrorResponse': {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean', 'example': False},
                'error': {'type': 'string', 'example': '错误信息'}
            }
        }
    }


def _extract_tags(routes, docs_base_path: str) -> list:
    """提取标签定义"""
    tags = {}
    blueprints = set(r.blueprint for r in routes if r.blueprint)

    for blueprint in blueprints:
        doc_path = f"{docs_base_path}/{blueprint}.yaml"
        doc_data = load_blueprint_doc(doc_path)
        if doc_data is None:
            doc_data = {}

        if doc_data and 'tags' in doc_data:
            for tag in doc_data['tags']:
                tags[tag['name']] = tag

    return list(tags.values())
