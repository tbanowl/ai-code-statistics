from typing import Optional


def scheduled(cron: str, job_id: str, name: Optional[str] = None, enabled: bool = True):
    def decorator(cls):
        cls._schedule_meta = {
            "cron": cron,
            "job_id": job_id,
            "name": name or cls.__name__,
            "enabled": enabled,
        }
        return cls

    return decorator
