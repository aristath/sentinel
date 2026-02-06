from sentinel_ml.api.routers import analytics_router, jobs_router, ml_router


def test_router_prefixes():
    assert ml_router.prefix == "/ml"
    assert analytics_router.prefix == "/analytics"
    assert jobs_router.prefix == "/jobs"
