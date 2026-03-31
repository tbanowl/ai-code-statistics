# tests/unit/test_swagger/test_scanner.py
import pytest
from flask import Flask
from core.swagger.scanner import scan_routes, RouteInfo


def test_scan_routes_empty_app():
    """测试空应用的扫描"""
    app = Flask(__name__)

    routes = scan_routes(app)

    assert routes == []


def test_scan_routes_single_get_route():
    """测试单个 GET 路由扫描"""
    app = Flask(__name__)

    @app.route('/test')
    def test_endpoint():
        return 'ok'

    routes = scan_routes(app)

    assert len(routes) == 1
    assert routes[0].path == '/test'
    assert 'GET' in routes[0].methods


def test_scan_routes_multiple_methods():
    """测试多方法路由扫描"""
    app = Flask(__name__)

    @app.route('/multi', methods=['GET', 'POST'])
    def multi_endpoint():
        return 'ok'

    routes = scan_routes(app)

    assert len(routes) == 1
    assert routes[0].path == '/multi'
    assert 'GET' in routes[0].methods
    assert 'POST' in routes[0].methods


def test_scan_routes_blueprint():
    """测试蓝图路由扫描"""
    from flask import Blueprint

    app = Flask(__name__)
    bp = Blueprint('test', __name__, url_prefix='/api')

    @bp.route('/list')
    def list_items():
        return []

    app.register_blueprint(bp)

    routes = scan_routes(app)

    api_routes = [r for r in routes if r.path.startswith('/api')]
    assert len(api_routes) >= 1
