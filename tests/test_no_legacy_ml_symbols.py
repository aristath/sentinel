from pathlib import Path

BANNED_STRINGS = [
    "app.include_router(ml_router",
    "app.include_router(regime_router",
    '"ml:retrain"',
    '"ml:monitor"',
    '"analytics:regime"',
]


def test_no_legacy_ml_symbols_in_monolith_runtime_files():
    runtime_files = [
        Path("sentinel/app.py"),
        Path("sentinel/jobs/runner.py"),
        Path("sentinel/api/routers/__init__.py"),
    ]
    contents = "\n".join(path.read_text() for path in runtime_files)
    for banned in BANNED_STRINGS:
        assert banned not in contents
