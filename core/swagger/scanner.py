"""
路由扫描器 - 从 Flask 应用提取路由信息
"""
from flask import Flask
from werkzeug.routing import Rule
from dataclasses import dataclass, field
from typing import List, Set, Optional


@dataclass
class RouteInfo:
    """路由元数据"""
    path: str                     # 路径
    methods: Set[str]              # HTTP 方法
    function_name: str            # 函数名
    blueprint: Optional[str] = None         # 蓝图名称
    parameters: List[str] = field(default_factory=list)  # 参数列表
    docstring: Optional[str] = None         # 函数文档字符串


def scan_routes(app: Flask) -> List[RouteInfo]:
    """
    扫描 Flask 应用的所有路由

    Args:
        app: Flask 应用实例

    Returns:
        RouteInfo 列表
    """
    routes = []

    for rule in app.url_map.iter_rules():
        if _should_skip_rule(rule):
            continue

        route_info = _extract_route_info(rule, app)
        if route_info:
            routes.append(route_info)

    return routes


def _should_skip_rule(rule: Rule) -> bool:
    """判断是否跳过该路由"""
    if '/swagger' in rule.rule or '/flasgger' in rule.rule:
        return True
    if rule.rule in ('/', '/<path:filename>', '/health'):
        return True
    if rule.rule.startswith('/static'):
        return True
    return False


def _extract_route_info(rule: Rule, app: Flask) -> Optional[RouteInfo]:
    """从 Flask 规则提取路由信息"""
    endpoint = app.view_functions.get(rule.endpoint)
    if not endpoint:
        return None

    return RouteInfo(
        path=rule.rule,
        methods=set(rule.methods) - {'HEAD', 'OPTIONS'},
        function_name=endpoint.__name__,
        blueprint=_get_blueprint_name(rule),
        parameters=_extract_parameters(rule),
        docstring=endpoint.__doc__
    )


def _get_blueprint_name(rule: Rule) -> Optional[str]:
    """从端点名称提取蓝图名称"""
    parts = rule.endpoint.split('.')
    if len(parts) > 1 and parts[1] != 'static':
        return parts[0]
    return None


def _extract_parameters(rule: Rule) -> List[str]:
    """从规则提取路径参数"""
    if not rule.arguments:
        return []
    return list(rule.arguments)
