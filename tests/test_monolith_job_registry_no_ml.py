from sentinel.jobs.runner import TASK_REGISTRY


def test_monolith_task_registry_has_no_ml_jobs():
    assert "ml:retrain" not in TASK_REGISTRY
    assert "ml:monitor" not in TASK_REGISTRY
    assert "analytics:regime" not in TASK_REGISTRY
