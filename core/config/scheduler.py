from typing import Dict


class SchedulerConfigLoader:
    @staticmethod
    def load(config: Dict) -> Dict:
        scheduler_config = config.get("scheduler", {})

        defaults = {"enabled": False, "timezone": "Asia/Shanghai", "jobs": {}}

        for key, value in defaults.items():
            if key not in scheduler_config:
                scheduler_config[key] = value

        return scheduler_config
