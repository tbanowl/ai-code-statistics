"""
Swagger 文档生成脚本
"""

import sys
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from flask import Flask
from core.config.loader import load_config_by_path
from core.swagger.generator import generate_swagger_spec


def generate(swagger_config: dict[str, Any] | None = None) -> str:
    """生成 Swagger 文档配置"""
    config = load_config_by_path(None)

    cfg: dict[str, Any] = (
        dict(swagger_config)
        if swagger_config is not None
        else dict(config.get("swagger", {}))
    )

    app = Flask(__name__)

    from api.routes.stats import stats_bp
    from api.routes.git_ai import git_ai_bp
    from api.routes.git_ai_worker import metrics_bp, cas_bp, oauth_bp, releases_bp
    from api.routes.scheduler import scheduler_bp
    from api.routes.authorship_notes import git_notes_rest_bp
    from api.routes.stats_repo import stats_repo_bp

    app.register_blueprint(stats_bp)
    app.register_blueprint(git_ai_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(cas_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(releases_bp)
    app.register_blueprint(scheduler_bp)
    app.register_blueprint(git_notes_rest_bp)
    app.register_blueprint(stats_repo_bp)

    spec = generate_swagger_spec(
        app,
        docs_base_path=cfg.get("docs_path", "docs/swagger/api"),
        api_config={
            "title": cfg.get("title", "API Documentation"),
            "version": cfg.get("version", "1.0.0"),
            "description": cfg.get("description", ""),
        },
    )

    output_path = cfg.get("output_path", "swagger_config.json")

    output_file = Path(output_path)
    print(f"output path: {output_path}")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)

    print(f"Swagger 配置已生成: {output_path}")

    return str(output_path)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="生成 Swagger API 文档")
    parser.add_argument("--output", help="输出文件路径", default="swagger_config.json")
    args = parser.parse_args()

    generate({"output_path": args.output})


if __name__ == "__main__":
    main()
