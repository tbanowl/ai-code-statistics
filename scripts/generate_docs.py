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

    print(f"Swagger 配置已生成: {output_path}")

    return str(output_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='生成 Swagger API 文档')
    parser.add_argument('--output', help='输出文件路径', default='swagger_config.json')
    args = parser.parse_args()

    generate({'output_path': args.output})


if __name__ == '__main__':
    main()
