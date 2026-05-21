import importlib


def _config(job_config=None, codeup_config=None):
    return {
        "scheduler": {
            "jobs": {
                "codeup_merge_authorship": job_config or {"enabled": True}
            }
        },
        "codeup_webhook": codeup_config or {"repo_cache_dir": ".cache/codeup_repos"},
    }


class FakeService:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def process_next_task(self):
        self.calls += 1
        return self.results.pop(0)


def test_codeup_merge_authorship_task_has_schedule_metadata():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )

    assert module.CodeupMergeAuthorshipTask._schedule_meta == {
        "cron": "*/2 * * * *",
        "job_id": "codeup_merge_authorship",
        "name": "Codeup Merge AI归属重算",
        "enabled": True,
    }


def test_codeup_merge_authorship_task_skips_when_scheduler_job_disabled():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )
    task = module.CodeupMergeAuthorshipTask(
        _config(job_config={"enabled": False, "batch_size": 10})
    )

    assert task.execute() == {"success": True, "processed": 0, "skipped": True}


def test_codeup_merge_authorship_task_processes_until_scheduler_batch_limit():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )
    service = FakeService(
        [
            {"success": True, "processed": 1},
            {"success": True, "processed": 1},
            {"success": True, "processed": 1},
            {"success": True, "processed": 1},
        ]
    )
    task = module.CodeupMergeAuthorshipTask(
        _config(
            job_config={"enabled": True, "batch_size": 3},
            codeup_config={"repo_cache_dir": ".cache/codeup_repos", "max_attempts": 5},
        ),
        service_factory=lambda codeup_config: service,
    )

    assert task.execute() == {"success": True, "processed": 3, "failed": 0}
    assert service.calls == 3


def test_codeup_merge_authorship_task_stops_when_no_task():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )
    service = FakeService(
        [
            {"success": True, "processed": 1},
            {"success": True, "processed": 0},
            {"success": True, "processed": 1},
        ]
    )

    task = module.CodeupMergeAuthorshipTask(
        _config(job_config={"enabled": True, "batch_size": 10}),
        service_factory=lambda codeup_config: service,
    )

    assert task.execute() == {"success": True, "processed": 1, "failed": 0}
    assert service.calls == 2


def test_codeup_merge_authorship_task_counts_failures():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )
    service = FakeService(
        [
            {"success": False, "processed": 1, "error": "boom"},
            {"success": True, "processed": 0},
        ]
    )

    task = module.CodeupMergeAuthorshipTask(
        _config(job_config={"enabled": True, "batch_size": 10}),
        service_factory=lambda codeup_config: service,
    )

    assert task.execute() == {"success": False, "processed": 1, "failed": 1}


def test_codeup_merge_authorship_task_counts_skipped_results_separately():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )
    service = FakeService(
        [
            {"success": True, "processed": 1, "skipped": True},
            {"success": True, "processed": 1},
            {"success": True, "processed": 0},
        ]
    )

    task = module.CodeupMergeAuthorshipTask(
        _config(job_config={"enabled": True, "batch_size": 10}),
        service_factory=lambda codeup_config: service,
    )

    assert task.execute() == {"success": True, "processed": 2, "failed": 0, "skipped": 1}


def test_codeup_merge_authorship_task_defaults_invalid_batch_size_to_one():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )
    service = FakeService(
        [
            {"success": True, "processed": 1},
            {"success": True, "processed": 1},
        ]
    )

    task = module.CodeupMergeAuthorshipTask(
        _config(job_config={"enabled": True, "batch_size": "bad"}),
        service_factory=lambda codeup_config: service,
    )

    assert task.execute() == {"success": True, "processed": 1, "failed": 0}
    assert service.calls == 1


def test_codeup_merge_authorship_task_defaults_less_than_one_batch_size_to_one():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )
    service = FakeService(
        [
            {"success": True, "processed": 1},
            {"success": True, "processed": 1},
        ]
    )

    task = module.CodeupMergeAuthorshipTask(
        _config(job_config={"enabled": True, "batch_size": 0}),
        service_factory=lambda codeup_config: service,
    )

    assert task.execute() == {"success": True, "processed": 1, "failed": 0}
    assert service.calls == 1


def test_codeup_merge_authorship_task_counts_released_results_separately():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )
    service = FakeService(
        [
            {"success": True, "processed": 1, "released": True, "reason": "missing ssh key for Codeup merge authorship"},
            {"success": True, "processed": 0},
        ]
    )

    task = module.CodeupMergeAuthorshipTask(
        _config(job_config={"enabled": True, "batch_size": 10}),
        service_factory=lambda codeup_config: service,
    )

    assert task.execute() == {"success": True, "processed": 1, "failed": 0, "released": 1}


def test_codeup_merge_authorship_task_passes_business_config_to_factory():
    module = importlib.import_module(
        "core.scheduler.tasks.codeup_merge_authorship_task"
    )
    service = FakeService([{"success": True, "processed": 0}])
    received_configs = []
    business_config = {
        "enabled": False,
        "repo_cache_dir": ".cache/codeup_repos",
        "max_attempts": 3,
    }

    def factory(codeup_config):
        received_configs.append(codeup_config)
        return service

    task = module.CodeupMergeAuthorshipTask(
        _config(
            job_config={"enabled": True, "batch_size": 10},
            codeup_config=business_config,
        ),
        service_factory=factory,
    )

    assert task.execute() == {"success": True, "processed": 0, "failed": 0}
    assert received_configs == [business_config]
