"""
YAML 文档加载器 - 加载和解析 API 文档
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from core.swagger.scanner import RouteInfo


def load_blueprint_doc(file_path: str) -> Optional[Dict[str, Any]]:
    """加载 Blueprint 的 YAML 文档文件"""
    path = Path(file_path)

    if not path.exists():
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"YAML 解析错误 {file_path}: {e}")
    except Exception as e:
        raise ValueError(f"加载文档失败 {file_path}: {e}")


def merge_with_route(route_info: RouteInfo, doc_data: Dict[str, Any]) -> Dict[str, Any]:
    """合并路由信息和文档数据"""
    endpoints = doc_data.get('endpoints', {})
    path_doc = endpoints.get(route_info.path, {})

    method_doc = None
    for method in route_info.methods:
        if method in path_doc:
            method_doc = path_doc[method]
            break
    
    merged = {
        'path': route_info.path.replace('<', '{').replace('>', '}'),
        'methods': list(route_info.methods),
        'function_name': route_info.function_name,
        'blueprint': route_info.blueprint,
    }

    if method_doc:
        merged.update(method_doc)
    else:
        if route_info.docstring:
            merged['summary'] = route_info.docstring.split('\n')[0].strip()
            merged['description'] = route_info.docstring.strip()

    return merged
