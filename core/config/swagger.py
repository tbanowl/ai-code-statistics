def swagger_setup(app, config, main_logger):
    swagger_config = config.get("swagger", {})
    if not swagger_config.get("enabled"):
        return

    from flasgger import Swagger
    import json

    # 尝试从生成的配置文件加载 Swagger 模板
    swagger_config_file = swagger_config.get("output_path", "swagger_config.json")
    try:
        with open(swagger_config_file, "r", encoding="utf-8") as f:
            swagger_template = json.load(f)
        main_logger.info(f"从 {swagger_config_file} 加载 Swagger 配置")
    except FileNotFoundError:
        main_logger.warning(
            f"Swagger 配置文件不存在: {swagger_config_file}，使用默认配置"
        )
        # 使用默认配置
        swagger_template = {
            "swagger": "2.0",
            "info": {
                "title": swagger_config.get("title", "API"),
                "version": swagger_config.get("version", "1.0.0"),
                "description": swagger_config.get("description", ""),
                "contact": swagger_config.get("contact", {}),
                "license": swagger_config.get("license", {}),
            },
            "host": f"{config.get('web', {}).get('host', '0.0.0.0')}:{config.get('web', {}).get('port', 8888)}",
            "basePath": "/",
            "schemes": ["http", "https"],
            "consumes": ["application/json"],
            "produces": ["application/json"],
            "tags": [
            ],
            "definitions": {
                "SuccessResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": True},
                        "data": {"type": "object"},
                    },
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": False},
                        "error": {"type": "string", "example": "错误信息"},
                    },
                },
            },
        }

    Swagger(
        app,
        template=swagger_template,
        config={
            "headers": [],
            "specs": [
                {
                    "endpoint": "apispec",
                    "route": "/swagger.json",
                    "rule_filter": lambda rule: True,
                    "model_filter": lambda tag: True,
                }
            ],
            "static_url_path": "/flasgger_static",
            "swagger_ui": True,
            "specs_route": "/swagger",
        },
    )
    main_logger.info(
        "Swagger UI 已启用，访问地址: http://{}:{}/swagger".format(
            config.get("web", {}).get("host", "0.0.0.0"),
            config.get("web", {}).get("port", 8888),
        )
    )

