import yaml
import os
from typing import Dict, Any


class ConfigLoader:
    """配置文件加载器"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """加载配置文件并处理环境变量"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 递归处理环境变量替换
        self._replace_env_vars(self.config)

        # 验证配置
        self._validate_config()

        return self.config

    def _replace_env_vars(self, obj: Any) -> Any:
        """递归替换配置中的环境变量占位符"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = self._replace_env_vars(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = self._replace_env_vars(item)
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]
            default_value = None
            if ":" in env_var:
                env_var, default_value = env_var.split(":", 1)
            return os.getenv(env_var, default_value)
        return obj

    def _validate_config(self) -> None:
        """验证配置完整性"""
        if not self.config.get('features', {}).get('enabled'):
            raise ValueError("Features not enabled")

        git_type = self.config.get('git', {}).get('type')
        if git_type not in ['gitlab', 'github']:
            raise ValueError(f"Unsupported git provider: {git_type}")

        db_type = self.config.get('database', {}).get('type')
        if db_type not in ['postgresql', 'mysql', 'sqlite']:
            raise ValueError(f"Unsupported database: {db_type}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的路径"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
