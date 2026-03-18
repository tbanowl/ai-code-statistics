# Swagger 实现重构 - 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 将 Swagger 文档从代码注释分离到 YAML 文件，通过反射自动生成文档配置

**架构:** YAGNI + 反射驱动。扫描 Flask 路由 → 提取基础信息 → 与 YAML 合并 → 生成 Swagger 配置

**技术栈:** Flask, Flasgger, PyYAML, pytest

---

## 准备工作

### Task 1: 创建目录结构

**Files:**
- Create: `core/swagger/__init__.py`
- Create: `core/swagger/scanner.py`
- Create: `core/swagger/loader.py`
- Create: `core/swagger/generator.py`
- Create: `scripts/generate_docs.py`
- Create: `docs/api/stats.yaml`
- Create: `tests/unit/test_swagger/__init__.py`
- Create: `tests/unit/test_swagger/test_scanner.py`
- Create: `tests/unit/test_swagger/test_loader.py`
- Create: `tests/unit/test_swagger/test_generator.py`

**Step 1: 创建目录**

```bash
mkdir -p core/swagger
mkdir -p scripts
mkdir -p docs/api
mkdir -p tests/unit/test_swagger
```

**Step 2: 验证目录创建**

```bash
ls -la core/ scripts/ docs/api/ tests/unit/test_swagger/
```
Expected: 显示创建的目录结构

**Step 3: 创建空的 __init__.py 文件**

```bash
touch core/swagger/__init__.py
touch tests/unit/test_swagger/__init__.py
```

**Step 4: 提交**

```bash
git add core/swagger/__init__.py tests/unit/test_swagger/__init__.py
git commit -m "feat: create swagger module directory structure"
```

---

## 核心模块实现

### Task 2: 实现路由扫描器 - 基础测试

**Files:**
- Create: `core/swagger/scanner.py`
- Test: `tests/unit/test_swagger/test_scanner.py`

**Step 1: 写失败的测试 - 基础路由扫描**

```python
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
    app = Flask(__name__)
    bp = Blueprint('test', __name__, url_prefix='/api')

    @bp.route('/list')
    def list_items():
        return []

    app.register_blueprint(bp)

    routes = scan_routes(app)

    api_routes = [r for r in routes if r.path.startswith('/api')]
    assert len(api_routes) >= 1
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/unit/test_swagger/test_scanner.py -v
```
Expected: FAIL with "module not found" 或 "function not defined"

**Step 3: 创建最简实现**

```python
# core/swagger/scanner.py
"""
路由扫描器 - 从 Flask 应用提取路由信息
"""
from flask import App
from werkzeug.routing import Rule
from dataclasses import dataclass
from typing import List, Set


@dataclass
class RouteInfo:
    """路由元数据"""
    path: str                     # 路径
    methods: Set[str]              # HTTP 方法
    function_name: str            # 函数名
    blueprint: str = None         # 蓝图名称
    parameters: List[str] = None  # 参数列表
    docstring: str = None         # 函数文档字符串


def scan_routes(app: App) -> List[RouteInfo]:
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

        route_info = _extract_route_info(rule)
        if route_info:
            routes.append(route_info)

    return routes


def _should_skip_rule(rule: Rule) -> bool:
    """判断是否跳过该路由"""
    if '/swagger' in rule.rule or '/flasgger' in rule.rule:
        return True
    if rule.rule in ('/', '/<path:filename>', '/health'):
        return True
    return False


def _extract_route_info(rule: Rule) -> RouteInfo:
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


def _get_blueprint_name(rule: Rule) -> str:
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
```

**Step 4: 修正导入并运行测试**

```bash
pytest tests/unit/test_swagger/test_scanner.py -v
```
Expected: 部分 PASS

**Step 5: 提交**

```bash
git add core/swagger/scanner.py tests/unit/test_swagger/test_scanner.py
git commit -m "feat: implement route scanner with basic tests"
```

---

### Task 3: 实现 YAML 加载器

**Files:**
- Create: `core/swagger/loader.py`
- Test: `tests/unit/test_swagger/test_loader.py`

**Step 1: 写失败的测试**

```python
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

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
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
```

**Step 2: 运行测试**

```bash
pytest tests/unit/test_swagger/test_loader.py -v
```
Expected: FAIL

**Step 3: 实现加载器**

```python
# core/swagger/loader.py
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
        'path': route_info.path,
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
```

**Step 4: 运行测试**

```bash
pytest tests/unit/test_swagger/test_loader.py -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add core/swagger/loader.py tests/unit/test_swagger/test_loader.py
git commit -m "feat: implement YAML loader with test coverage"
```

---

### Task 4: 实现文档生成器

**Files:**
- Create: `core/swagger/generator.py`
- Test: `tests/unit/test_swagger/test_generator.py`

**Step 1: 写失败的测试**

```python
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
```

**Step 2: 运行测试**

```bash
pytest tests/unit/test_swagger/test_generator.py -v
```
Expected: FAIL

**Step 3: 实现生成器**

```python
# core/swagger/generator.py
"""
Swagger 文档生成器 - 合并扫描结果和 YAML 生成 Swagger 配置
"""
from flask import App
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
    app: App,
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
        doc_data = load_blueprint_doc(doc_path) if doc_path else {}

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

        if doc_data and 'tags' in doc_data:
            for tag in doc_data['tags']:
                tags[tag['name']] = tag

    return list(tags.values())
```

**Step 4: 运行测试**

```bash
pytest tests/unit/test_swagger/test_generator.py -v
```
Expected: PASS

**Step 5: 提交**

```bash
git add core/swagger/generator.py tests/unit/test_swagger/test_generator.py
git commit -m "feat: implement Swagger generator with test coverage"
```

---

## 集成与工具

### Task 5: 实现文档生成脚本

**Files:**
- Create: `scripts/generate_docs.py`

**Step 1: 实现生成脚本**

```python
# scripts/generate_docs.py
"""
Swagger 文档生成脚本
"""
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from flask import Flask
from core.config.loader import ConfigLoader
from core.swagger.generator import generate_swagger_spec


def generate(swagger_config: dict = None) -> str:
    """生成 Swagger 文档配置"""
    config_loader = ConfigLoader()
    config = config_loader.load()

    if swagger_config is None:
        swagger_config = config.get('swagger', {})

    app = Flask(__name__)

    from api.routes.stats import stats_bp
    from api.routes.projects import projects_bp
    from api.routes.git_ai import git_ai_bp
    from api.routes.git_ai_worker import metrics_bp

    app.register_blueprint(stats_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(git_ai_bp)
    app.register_blueprint(metrics_bp)

    spec = generate_swagger_spec(
        app,
        docs_base_path=swagger_config.get('docs_path', 'docs/api'),
        api_config={
            'title': swagger_config.get('title', 'API Documentation'),
            'version': swagger_config.get('version', '1.0.0'),
            'description': swagger_config.get('description', '')
        }
    )

    output_path = swagger_config.get('output_path', 'swagger_config.json')

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)

    print(f"✓ Swagger 配置已生成: {output_path}")

    return str(output_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='生成 Swagger API 文档')
    parser.add_argument('--output', help='输出文件路径', default='swagger_config.json')
    args = parser.parse_args()

    generate({'output_path': args.output})


if __name__ == '__main__':
    main()
```

**Step 2: 创建 YAML 文档**

```bash
cat > docs/api/stats.yaml << 'EOF'
tags:
  - name: stats
    description: 统计分析 API

endpoints:
  /analyze:
    POST:
      summary: 执行统计分析
      description: 根据指定的日期范围和部门，统计分析 AI 代码占比
      parameters:
        - name: body
          in: body
          required: true
EOF
```

```bash
cat > docs/api/projects.yaml << 'EOF'
tags:
  - name: projects
    description: 项目管理 API
EOF
```

**Step 3: 提交**

```bash
git add scripts/generate_docs.py docs/api/
git commit -m "feat: add docs generation script and YAML docs"
```

---

### Task 6: 修改 app.py 集成

**Files:**
- Modify: `app.py`

**Step 1: 读取生成的配置文件**

```python
# 在 app.py 中修改 swagger 初始化部分
if swagger_config.get('enabled', False):
    import json
    from flasgger import Swagger

    swagger_config_file = swagger_config.get('output_path', 'swagger_config.json')
    try:
        with open(swagger_config_file, 'r', encoding='utf-8') as f:
            swagger_template = json.load(f)
    except FileNotFoundError:
        logger.warning(f'Swagger 配置文件不存在: {swagger_config_file}')
        # 使用默认配置
        ...

    Swagger(app, template=swagger_template, config={
        'headers': [],
        'specs': [{'endpoint': 'apispec', 'route': '/swagger.json'}],
        'static_url_path': '/flasgger_static',
        'swagger_ui': True,
        'specs_route': '/swagger'
    })
```

**Step 2: 测试**

```bash
python scripts/generate_docs.py
python app.py
```

**Step 3: 提交**

```bash
git add app.py
git commit -m "refactor: use generated Swagger config"
```

---

## 清理

### Task 7: 移除代码中的 Swagger 注释

**Files:**
- Modify: `api/routes/stats.py` 等

清理每个路由文件中的 YAML 注释，保留简单 docstring

**Step 1: 提交**

```bash
git add api/routes/
git commit -m "cleanup: remove Swagger YAML from code"
```

---

## 总结

完成以上任务后会实现：
- 文档与代码分离
- 自动提取基础信息
- YAML 按蓝图组织
- 简单的生成流程
