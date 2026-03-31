import yaml
import os
from typing import Dict, Any, Optional

config_data: Dict[str, Any] = {}

def load_config() -> Dict[str, Any]:
    return load_config_by_path(None)


def load_config_by_path(config_path: Optional[str]) -> Dict[str, Any]:
    global config_data
    if config_data:
        return config_data
    if not config_path:
        config_path = "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    
    print('----------------------------- load config data -----------------------------')
    # 递归处理环境变量替换
    _replace_env_vars(config_data)

    # 验证配置
    _validate_config(config_data)

    return config_data

def _validate_config(config) -> None:
    """验证配置完整性"""
    db_url = config.get('database', {}).get('url')
    if not db_url:
        raise ValueError("No database url")


def _replace_env_vars(obj: Any) -> Any:
    """递归替换配置中的环境变量占位符"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = _replace_env_vars(value)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = _replace_env_vars(item)
    elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        env_var = obj[2:-1]
        default_value = None
        if ":" in env_var:
            env_var, default_value = env_var.split(":", 1)
        return os.getenv(env_var, default_value)
    return obj

