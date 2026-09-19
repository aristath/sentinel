"""Complete contract tests for Sentinel's MCP transport adapter."""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx2
import pytest
from fastapi import HTTPException
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.mcpserver.exceptions import ToolError

import sentinel.app as app_module
import sentinel.mcp_server as server

app = app_module.app
DEPS = SimpleNamespace(marker="shared-sentinel-dependencies")
PASSTHROUGH = object()
ORIGINAL_DEPS = server._deps

EXPECTED_TOOLS = {
    "sentinel_status",
    "portfolio_get",
    "portfolio_composition_get",
    "portfolio_performance_get",
    "portfolio_period_stats_get",
    "portfolio_projection_get",
    "securities_overview_get",
    "securities_list",
    "security_get",
    "security_prices_get",
    "security_prices_sync",
    "security_add",
    "security_update",
    "security_remove",
    "portfolio_plan_get",
    "portfolio_alignment_get",
    "trades_get",
    "cashflow_summary_get",
    "markets_get",
    "exchange_rates_get",
    "settings_get",
    "setting_set",
    "strategy_settings_set",
    "job_status_get",
    "job_schedules_get",
    "job_history_get",
    "job_run",
    "job_schedule_update",
    "tasks_list",
    "task_get",
    "task_create",
    "task_meta_update",
    "task_delete",
    "task_validate",
    "task_files_list",
    "task_file_get",
    "task_file_save",
    "task_file_delete",
    "task_runs_enqueue",
    "task_runs_get",
    "task_run_get",
    "task_run_stop",
    "ai_status_get",
    "ai_models_get",
    "ai_prompt",
    "ai_units_get",
    "ai_history_get",
    "ai_artifact_get",
    "ai_artifact_files_list",
    "ai_artifact_file_get",
    "ai_artifact_search",
    "ai_research_run",
    "forecast_status_get",
    "forecast_get",
    "security_buy",
    "security_sell",
    "backup_status_get",
}


@dataclass(frozen=True)
class AdapterCase:
    case_id: str
    tool: str
    module: str
    operation: str
    arguments: dict[str, Any]
    expected_args: tuple[Any, ...]
    result: Any
    output: Any = PASSTHROUGH


def _dict_result(tool: str) -> dict[str, Any]:
    return {"adapter": tool}


def _list_result(tool: str) -> list[dict[str, Any]]:
    return [{"adapter": tool}]


def _case(
    tool: str,
    module: str,
    operation: str,
    arguments: dict[str, Any],
    expected_args: tuple[Any, ...],
    *,
    result: Any | None = None,
    output: Any = PASSTHROUGH,
    suffix: str = "default",
) -> AdapterCase:
    return AdapterCase(
        case_id=f"{tool}-{suffix}",
        tool=tool,
        module=module,
        operation=operation,
        arguments=arguments,
        expected_args=expected_args,
        result=_dict_result(tool) if result is None else result,
        output=output,
    )


STRATEGY_VALUES = {
    "strategy_min_opp_score": 0.6,
    "strategy_ideal_qualifying_threshold": 0.65,
    "strategy_core_timing_min_score": 0.3,
    "strategy_core_timing_min_dip_score": 0.2,
    "strategy_fallback_wait_days": 30.0,
    "strategy_entry_t1_dd": -0.10,
    "strategy_entry_t2_dd": -0.16,
    "strategy_entry_t3_dd": -0.22,
    "strategy_entry_memory_days": 45.0,
    "strategy_memory_max_boost": 0.12,
    "strategy_opportunity_addon_threshold": 0.75,
    "strategy_max_opportunity_buys_per_cycle": 1.0,
    "strategy_max_new_opportunity_buys_per_cycle": 1.0,
}

BASE_CASES = [
    _case("portfolio_get", "portfolio_api", "get_portfolio", {}, (DEPS,)),
    _case("portfolio_composition_get", "portfolio_api", "get_portfolio_composition", {}, (DEPS,)),
    _case("portfolio_performance_get", "portfolio_api", "get_portfolio_pnl_history", {}, (DEPS, "1Y")),
    _case("portfolio_period_stats_get", "portfolio_api", "get_portfolio_period_stats", {}, (DEPS,)),
    _case(
        "portfolio_projection_get",
        "portfolio_api",
        "get_portfolio_value_projection",
        {},
        (DEPS, 10, None),
    ),
    _case(
        "securities_overview_get",
        "securities_api",
        "get_unified_view",
        {},
        (DEPS, "1Y", None, False, False),
        result=_list_result("securities_overview_get"),
    ),
    _case(
        "securities_list",
        "securities_api",
        "get_securities",
        {},
        (DEPS,),
        result=_list_result("securities_list"),
    ),
    _case("security_get", "securities_api", "get_security", {"symbol": "AIR.EU"}, ("AIR.EU", DEPS)),
    _case(
        "security_prices_get",
        "securities_api",
        "get_prices",
        {"symbol": "AIR.EU"},
        ("AIR.EU", 365),
        result=_list_result("security_prices_get"),
    ),
    _case(
        "security_prices_sync",
        "securities_api",
        "sync_prices",
        {"symbol": "AIR.EU"},
        ("AIR.EU", 365),
        result={"synced": 10},
    ),
    _case(
        "security_add",
        "securities_api",
        "add_security",
        {"symbol": "AIR.EU"},
        ({"symbol": "AIR.EU"}, DEPS),
    ),
    _case(
        "security_update",
        "securities_api",
        "update_security",
        {"symbol": "AIR.EU", "changes": {"allow_buy": False, "future_field": {"raw": True}}},
        ("AIR.EU", {"allow_buy": False, "future_field": {"raw": True}}, DEPS),
    ),
    _case(
        "security_remove",
        "securities_api",
        "delete_security",
        {"symbol": "AIR.EU"},
        ("AIR.EU", DEPS, False),
    ),
    _case("portfolio_plan_get", "planner_api", "get_recommendations", {}, (DEPS, None)),
    _case("portfolio_alignment_get", "planner_api", "get_rebalance_summary", {}, ()),
    _case(
        "trades_get",
        "trading_api",
        "get_trades",
        {},
        (DEPS, None, None, None, None, 100, 0),
    ),
    _case("cashflow_summary_get", "trading_api", "get_cashflows", {}, (DEPS,)),
    _case("markets_get", "system_api", "get_markets_status", {}, (DEPS,)),
    _case("exchange_rates_get", "system_api", "get_exchange_rates", {}, ()),
    _case("settings_get", "settings_api", "get_settings", {}, (DEPS,)),
    _case(
        "setting_set",
        "settings_api",
        "set_setting",
        {"key": "trading_mode", "value": "research"},
        ("trading_mode", {"value": "research"}, DEPS),
    ),
    _case(
        "strategy_settings_set",
        "settings_api",
        "set_settings_batch",
        {"values": STRATEGY_VALUES},
        ({"values": STRATEGY_VALUES}, DEPS),
    ),
    _case("job_status_get", "jobs_api", "get_jobs", {}, ()),
    _case("job_schedules_get", "jobs_api", "get_job_schedules", {}, (DEPS,)),
    _case("job_history_get", "jobs_api", "get_job_history", {}, (DEPS, None, 50)),
    _case(
        "job_run",
        "jobs_api",
        "run_job_endpoint",
        {"job_type": "sync:portfolio"},
        ("sync:portfolio",),
    ),
    _case(
        "job_schedule_update",
        "jobs_api",
        "update_job_schedule",
        {"job_type": "sync:portfolio", "schedule": {"interval_minutes": 30, "raw": "preserved"}},
        ("sync:portfolio", {"interval_minutes": 30, "raw": "preserved"}, DEPS),
    ),
    _case(
        "tasks_list",
        "tasks_api",
        "tasks_list",
        {},
        (),
        result=_list_result("tasks_list"),
    ),
    _case("task_get", "tasks_api", "task_get", {"task_id": "analyze-security"}, ("analyze-security",)),
    _case(
        "task_create",
        "tasks_api",
        "tasks_create",
        {"name": "New task"},
        ({"name": "New task"},),
    ),
    _case(
        "task_meta_update",
        "tasks_api",
        "task_meta_save",
        {
            "task_id": "analyze-security",
            "changes": {"statePath": "state.json", "schedulePolicy": {"runWhen": "idle"}, "future": 3},
        },
        (
            "analyze-security",
            {"statePath": "state.json", "schedulePolicy": {"runWhen": "idle"}, "future": 3},
        ),
    ),
    _case(
        "task_delete",
        "tasks_api",
        "task_delete",
        {"task_id": "custom-task"},
        ("custom-task",),
        output={"status": "deleted", "task_id": "custom-task"},
    ),
    _case(
        "task_validate",
        "tasks_api",
        "task_validate",
        {"task_id": "analyze-security"},
        ("analyze-security",),
    ),
    _case(
        "task_files_list",
        "tasks_api",
        "task_files",
        {"task_id": "analyze-security"},
        ("analyze-security",),
        result=_list_result("task_files_list"),
    ),
    _case(
        "task_file_get",
        "tasks_api",
        "task_file_get",
        {"task_id": "analyze-security", "name": "task.js"},
        ("analyze-security", "task.js"),
    ),
    _case(
        "task_file_save",
        "tasks_api",
        "task_file_save",
        {"task_id": "analyze-security", "name": "task.js", "content": "source"},
        ("analyze-security", "task.js", {"content": "source"}),
    ),
    _case(
        "task_file_delete",
        "tasks_api",
        "task_file_delete",
        {"task_id": "custom-task", "name": "notes.md"},
        ("custom-task", "notes.md"),
        output={"status": "deleted", "task_id": "custom-task", "name": "notes.md"},
    ),
    _case(
        "task_runs_enqueue",
        "tasks_api",
        "scheduler_enqueue",
        {"items": [{"task": "analyze-security"}]},
        ([{"task": "analyze-security"}],),
    ),
    _case(
        "task_runs_get",
        "tasks_api",
        "task_runs",
        {"task_id": "analyze-security"},
        ("analyze-security", 50),
        result=_list_result("task_runs_get"),
    ),
    _case("task_run_get", "tasks_api", "task_run_get", {"run_id": "run-1"}, ("run-1",)),
    _case("task_run_stop", "tasks_api", "task_run_stop", {"run_id": "run-1"}, ("run-1",)),
    _case("ai_status_get", "ai_api", "get_ai_status", {}, (DEPS,)),
    _case("ai_models_get", "ai_api", "get_ai_models", {}, (DEPS,)),
    _case(
        "ai_prompt",
        "ai_api",
        "create_ai_prompt",
        {"prompt": "Analyze AIR.EU"},
        ({"prompt": "Analyze AIR.EU"}, DEPS),
        result={"output": "Analysis"},
    ),
    _case("ai_units_get", "ai_api", "get_ai_units", {}, (DEPS, None, False)),
    _case("ai_history_get", "ai_api", "get_ai_history", {}, (DEPS, 50)),
    _case(
        "ai_artifact_get",
        "ai_api",
        "get_ai_artifact",
        {"kind": "security", "unit_key": "AIR.EU", "name": "report.md"},
        ("security", "AIR.EU", "report.md", DEPS),
    ),
    _case(
        "ai_artifact_files_list",
        "ai_api",
        "list_ai_artifact_files",
        {},
        ("",),
    ),
    _case(
        "ai_artifact_file_get",
        "ai_api",
        "get_ai_artifact_file",
        {"path": "analyze-security/AIR.EU.summary.md"},
        ("analyze-security/AIR.EU.summary.md",),
    ),
    _case(
        "ai_artifact_search",
        "ai_api",
        "search_ai_artifact_files",
        {"query": "battery"},
        ("battery", ""),
    ),
    _case(
        "ai_research_run",
        "ai_api",
        "create_ai_request",
        {"kind": "analyze", "unit_kind": "security", "unit_key": "AIR.EU"},
        ({"kind": "analyze", "unit_kind": "security", "unit_key": "AIR.EU"}, DEPS),
    ),
    _case("forecast_status_get", "forecasts_api", "get_forecast_status", {}, (DEPS,)),
    _case(
        "forecast_get",
        "forecasts_api",
        "get_symbol_forecast",
        {"symbol": "AIR.EU"},
        ("AIR.EU", DEPS),
    ),
    _case(
        "security_buy",
        "trading_api",
        "buy_security",
        {"symbol": "AIR.EU", "quantity": 2},
        ("AIR.EU", 2),
    ),
    _case(
        "security_sell",
        "trading_api",
        "sell_security",
        {"symbol": "AIR.EU", "quantity": 2},
        ("AIR.EU", 2),
    ),
    _case("backup_status_get", "backup_api", "get_backup_status", {}, (DEPS,)),
]

VARIANT_CASES = [
    _case(
        "portfolio_plan_get",
        "planner_api",
        "get_recommendations",
        {"minimum_trade_value_eur": 250.0},
        (DEPS, 250.0),
        suffix="minimum-trade-value",
    ),
    _case(
        "portfolio_performance_get",
        "portfolio_api",
        "get_portfolio_pnl_history",
        {"period": "ALL"},
        (DEPS, "ALL"),
        suffix="period",
    ),
    _case(
        "portfolio_projection_get",
        "portfolio_api",
        "get_portfolio_value_projection",
        {"years": 10, "monthly_net_deposit_eur": 321.5},
        (DEPS, 10, 321.5),
        suffix="override",
    ),
    _case(
        "securities_overview_get",
        "securities_api",
        "get_unified_view",
        {"period": "5Y", "as_of": "2026-09-01", "include_inactive": True, "inactive_only": True},
        (DEPS, "5Y", "2026-09-01", True, True),
        result=_list_result("securities_overview_get"),
        suffix="filters",
    ),
    _case(
        "security_prices_get",
        "securities_api",
        "get_prices",
        {"symbol": "AIR.EU", "days": 30},
        ("AIR.EU", 30),
        result=_list_result("security_prices_get"),
        suffix="days",
    ),
    _case(
        "trades_get",
        "trading_api",
        "get_trades",
        {
            "symbol": "AIR.EU",
            "side": "BUY",
            "start_date": "2026-01-01",
            "end_date": "2026-09-01",
            "limit": 7,
            "offset": 9,
        },
        (DEPS, "AIR.EU", "BUY", "2026-01-01", "2026-09-01", 7, 9),
        suffix="filters",
    ),
    _case(
        "setting_set",
        "settings_api",
        "set_setting",
        {"key": "strategy_min_opp_score", "value": True},
        ("strategy_min_opp_score", {"value": True}, DEPS),
        suffix="raw-strategy-value",
    ),
    _case(
        "strategy_settings_set",
        "settings_api",
        "set_settings_batch",
        {"values": {**STRATEGY_VALUES, "strategy_min_opp_score": True}},
        ({"values": {**STRATEGY_VALUES, "strategy_min_opp_score": True}}, DEPS),
        suffix="validation-delegated",
    ),
    _case(
        "job_history_get",
        "jobs_api",
        "get_job_history",
        {"job_type": "sync:prices", "limit": 3},
        (DEPS, "sync:prices", 3),
        suffix="filters",
    ),
    _case(
        "task_file_save",
        "tasks_api",
        "task_file_create",
        {"task_id": "custom-task", "name": "notes.md", "content": "notes", "create": True},
        ("custom-task", {"name": "notes.md", "content": "notes"}),
        suffix="create",
    ),
    _case(
        "task_runs_enqueue",
        "tasks_api",
        "scheduler_enqueue",
        {
            "items": [
                {"task": "analyze-security", "inputs": {"symbol": "AIR.EU"}},
                {
                    "task": "rate-portfolio",
                    "eligibleAt": 1_788_480_000,
                    "dedupeKey": "portfolio-1",
                    "future": {"preserved": True},
                },
            ]
        },
        (
            [
                {"task": "analyze-security", "inputs": {"symbol": "AIR.EU"}},
                {
                    "task": "rate-portfolio",
                    "eligibleAt": 1_788_480_000,
                    "dedupeKey": "portfolio-1",
                    "future": {"preserved": True},
                },
            ],
        ),
        suffix="batch-raw-fields",
    ),
    _case(
        "task_runs_get",
        "tasks_api",
        "task_runs",
        {"task_id": "rate-portfolio", "limit": 7},
        ("rate-portfolio", 7),
        result=_list_result("task_runs_get"),
        suffix="limit",
    ),
    _case(
        "ai_units_get",
        "ai_api",
        "get_ai_units",
        {"kind": "security", "stale_only": True},
        (DEPS, "security", True),
        suffix="filters",
    ),
    _case(
        "ai_prompt",
        "ai_api",
        "create_ai_prompt",
        {"prompt": "Analyze AIR.EU", "temperature": 0.2},
        ({"prompt": "Analyze AIR.EU", "temperature": 0.2}, DEPS),
        result={"output": "Analysis"},
        suffix="temperature",
    ),
    _case(
        "ai_history_get",
        "ai_api",
        "get_ai_history",
        {"limit": 7},
        (DEPS, 7),
        suffix="limit",
    ),
]


def _target(case: AdapterCase) -> tuple[Any, str]:
    return getattr(server, case.module), case.operation


def _unwrap_structured(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"result"}:
        return value["result"]
    return value


@pytest.fixture(autouse=True)
def shared_dependencies(monkeypatch):
    monkeypatch.setattr(server, "_deps", AsyncMock(return_value=DEPS))


@pytest.mark.asyncio
async def test_mcp_lists_exactly_the_complete_sentinel_tool_surface():
    async with Client(server.mcp) as client:
        result = await client.list_tools()

    assert {tool.name for tool in result.tools} == EXPECTED_TOOLS
    assert all(tool.description and tool.description.strip() for tool in result.tools)
    assert all(tool.output_schema is not None for tool in result.tools)
    for tool in result.tools:
        signature = inspect.signature(getattr(server, tool.name))
        assert set(tool.input_schema["properties"]) == set(signature.parameters), tool.name


def test_every_tool_has_success_and_failure_contract_cases():
    success_tools = {"sentinel_status", *(case.tool for case in BASE_CASES)}
    failure_tools = {"sentinel_status", *(case.tool for case in BASE_CASES)}
    assert success_tools == EXPECTED_TOOLS
    assert failure_tools == EXPECTED_TOOLS
    assert len(BASE_CASES) == len(EXPECTED_TOOLS) - 1


def test_mcp_is_mounted_before_the_spa_catch_all():
    paths = [route.path for route in app.routes]
    assert "/mcp" in paths
    assert paths.index("/mcp") < paths.index("/{path:path}")


@pytest.mark.asyncio
async def test_deps_delegates_to_the_application_dependency_provider(monkeypatch):
    deps = SimpleNamespace(real=True)
    provider = AsyncMock(return_value=deps)
    monkeypatch.setattr(server, "get_common_deps", provider)

    assert await ORIGINAL_DEPS() is deps
    provider.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (HTTPException(status_code=503, detail="dependencies unavailable"), "dependencies unavailable"),
        (ValueError("dependencies invalid"), "dependencies invalid"),
        (RuntimeError("dependencies failed"), "dependencies failed"),
    ],
)
async def test_deps_translates_expected_dependency_failures(monkeypatch, exception, message):
    monkeypatch.setattr(server, "get_common_deps", AsyncMock(side_effect=exception))

    with pytest.raises(ToolError, match=message):
        await ORIGINAL_DEPS()


@pytest.mark.asyncio
async def test_sentinel_status_merges_health_and_version(monkeypatch):
    health = AsyncMock(return_value={"status": "healthy", "broker_connected": True})
    version = AsyncMock(return_value={"version": "v-test"})
    monkeypatch.setattr(server.system_api, "health", health)
    monkeypatch.setattr(server.system_api, "version", version)

    async with Client(server.mcp) as client:
        result = await client.call_tool("sentinel_status", {})

    assert result.is_error is False
    assert result.structured_content == {
        "status": "healthy",
        "broker_connected": True,
        "version": "v-test",
    }
    health.assert_awaited_once_with(DEPS)
    version.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", BASE_CASES + VARIANT_CASES, ids=lambda case: case.case_id)
async def test_tool_delegates_exact_arguments_and_returns_result(monkeypatch, case):
    module, operation = _target(case)
    endpoint = AsyncMock(return_value=case.result)
    monkeypatch.setattr(module, operation, endpoint)

    async with Client(server.mcp) as client:
        result = await client.call_tool(case.tool, case.arguments)

    assert result.is_error is False
    expected_output = case.result if case.output is PASSTHROUGH else case.output
    assert _unwrap_structured(result.structured_content) == expected_output
    endpoint.assert_awaited_once_with(*case.expected_args)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception",
    [
        HTTPException(status_code=503, detail="health unavailable"),
        ValueError("health unavailable"),
        RuntimeError("health unavailable"),
    ],
    ids=["http", "value", "runtime"],
)
async def test_sentinel_status_reports_health_failure_without_calling_version(monkeypatch, exception):
    health = AsyncMock(side_effect=exception)
    version = AsyncMock(return_value={"version": "should-not-run"})
    monkeypatch.setattr(server.system_api, "health", health)
    monkeypatch.setattr(server.system_api, "version", version)

    async with Client(server.mcp) as client:
        result = await client.call_tool("sentinel_status", {})

    assert result.is_error is True
    assert "health unavailable" in result.content[0].text
    health.assert_awaited_once_with(DEPS)
    version.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception",
    [
        HTTPException(status_code=503, detail="version unavailable"),
        ValueError("version unavailable"),
        RuntimeError("version unavailable"),
    ],
    ids=["http", "value", "runtime"],
)
async def test_sentinel_status_reports_version_failure_after_health(monkeypatch, exception):
    health = AsyncMock(return_value={"status": "healthy"})
    version = AsyncMock(side_effect=exception)
    monkeypatch.setattr(server.system_api, "health", health)
    monkeypatch.setattr(server.system_api, "version", version)

    async with Client(server.mcp) as client:
        result = await client.call_tool("sentinel_status", {})

    assert result.is_error is True
    assert "version unavailable" in result.content[0].text
    health.assert_awaited_once_with(DEPS)
    version.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_operation", ["health", "version"])
async def test_sentinel_status_masks_unexpected_programming_errors(monkeypatch, failed_operation):
    health = AsyncMock(return_value={"status": "healthy"})
    version = AsyncMock(return_value={"version": "v-test"})
    failed = health if failed_operation == "health" else version
    failed.side_effect = KeyError("private status defect")
    monkeypatch.setattr(server.system_api, "health", health)
    monkeypatch.setattr(server.system_api, "version", version)

    async with Client(server.mcp) as client:
        result = await client.call_tool("sentinel_status", {})

    assert result.is_error is True
    assert result.content[0].text == "Error executing tool sentinel_status"
    assert "private status defect" not in result.content[0].text
    health.assert_awaited_once_with(DEPS)
    if failed_operation == "health":
        version.assert_not_awaited()
    else:
        version.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", BASE_CASES + VARIANT_CASES, ids=lambda case: case.case_id)
@pytest.mark.parametrize(
    ("exception_factory", "failure_kind"),
    [
        (lambda message: HTTPException(status_code=409, detail=message), "http"),
        (ValueError, "value"),
        (RuntimeError, "runtime"),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
async def test_every_tool_reports_downstream_failure(monkeypatch, case, exception_factory, failure_kind):
    module, operation = _target(case)
    message = f"{case.tool} {failure_kind} failure"
    endpoint = AsyncMock(side_effect=exception_factory(message))
    monkeypatch.setattr(module, operation, endpoint)

    async with Client(server.mcp) as client:
        result = await client.call_tool(case.tool, case.arguments)

    assert result.is_error is True
    assert message in result.content[0].text
    endpoint.assert_awaited_once_with(*case.expected_args)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", BASE_CASES + VARIANT_CASES, ids=lambda case: case.case_id)
async def test_every_tool_masks_unexpected_programming_errors(monkeypatch, case):
    module, operation = _target(case)
    message = f"{case.tool} private defect"
    endpoint = AsyncMock(side_effect=KeyError(message))
    monkeypatch.setattr(module, operation, endpoint)

    async with Client(server.mcp) as client:
        result = await client.call_tool(case.tool, case.arguments)

    assert result.is_error is True
    assert result.content[0].text == f"Error executing tool {case.tool}"
    assert message not in result.content[0].text
    endpoint.assert_awaited_once_with(*case.expected_args)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (HTTPException(status_code=409, detail="resource is active"), "resource is active"),
        (ValueError("invalid domain value"), "invalid domain value"),
        (RuntimeError("runtime unavailable"), "runtime unavailable"),
    ],
)
async def test_call_translates_expected_application_failures(exception, message):
    async def fail():
        raise exception

    with pytest.raises(ToolError, match=message):
        await server._call(fail())


@pytest.mark.asyncio
async def test_call_does_not_mask_unexpected_programming_errors():
    async def fail():
        raise KeyError("programming defect")

    with pytest.raises(KeyError, match="programming defect"):
        await server._call(fail())


@pytest.mark.asyncio
async def test_unknown_tool_name_returns_an_mcp_error():
    async with Client(server.mcp) as client:
        result = await client.call_tool("not_a_sentinel_tool", {})

    assert result.is_error is True
    assert "Unknown tool" in result.content[0].text


@pytest.mark.asyncio
async def test_required_arguments_are_enforced_before_endpoint_execution(monkeypatch):
    endpoints = []
    for case in BASE_CASES:
        module, operation = _target(case)
        endpoint = AsyncMock(return_value=case.result)
        monkeypatch.setattr(module, operation, endpoint)
        endpoints.append(endpoint)

    async with Client(server.mcp) as client:
        tools = await client.list_tools()
        schemas = {tool.name: tool.input_schema for tool in tools.tools}
        checked = 0
        for case, endpoint in zip(BASE_CASES, endpoints, strict=True):
            required = schemas[case.tool].get("required", [])
            for field in required:
                invalid_arguments = dict(case.arguments)
                invalid_arguments.pop(field, None)
                result = await client.call_tool(case.tool, invalid_arguments)
                assert result.is_error is True, f"{case.tool}.{field}"
                assert field in result.content[0].text, f"{case.tool}.{field}"
                checked += 1
            endpoint.assert_not_awaited()

    assert checked == 45


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "arguments", "module_name", "operation"),
    [
        ("security_get", {"symbol": 123}, "securities_api", "get_security"),
        (
            "security_prices_sync",
            {"symbol": "TEST.EU", "days": "many"},
            "securities_api",
            "sync_prices",
        ),
        ("task_runs_enqueue", {"items": {}}, "tasks_api", "scheduler_enqueue"),
        (
            "security_buy",
            {"symbol": "TEST.EU", "quantity": 1.5},
            "trading_api",
            "buy_security",
        ),
    ],
)
async def test_invalid_argument_types_are_rejected_before_execution(
    monkeypatch,
    tool,
    arguments,
    module_name,
    operation,
):
    endpoint = AsyncMock(return_value={"unexpected": "execution"})
    monkeypatch.setattr(getattr(server, module_name), operation, endpoint)

    async with Client(server.mcp) as client:
        result = await client.call_tool(tool, arguments)

    assert result.is_error is True
    endpoint.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "malformed_result"),
    [
        (next(case for case in BASE_CASES if case.tool == "portfolio_get"), []),
        (next(case for case in BASE_CASES if case.tool == "securities_list"), {"not": "a list"}),
        (next(case for case in BASE_CASES if case.tool == "setting_set"), {"status": {}}),
        (next(case for case in BASE_CASES if case.tool == "security_prices_sync"), {"synced": {}}),
    ],
    ids=["dict", "list", "string-values", "integer-values"],
)
async def test_structured_output_validation_rejects_wrong_endpoint_shape(monkeypatch, case, malformed_result):
    module, operation = _target(case)
    monkeypatch.setattr(module, operation, AsyncMock(return_value=malformed_result))

    async with Client(server.mcp) as client:
        result = await client.call_tool(case.tool, case.arguments)

    assert result.is_error is True


@pytest.mark.asyncio
async def test_open_payloads_preserve_unknown_fields_for_application_validation():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()

    schemas = {tool.name: tool.input_schema for tool in tools.tools}
    for tool_name, argument_name in (
        ("security_update", "changes"),
        ("job_schedule_update", "schedule"),
        ("task_meta_update", "changes"),
    ):
        payload_schema = schemas[tool_name]["properties"][argument_name]
        assert payload_schema["type"] == "object"
        assert payload_schema["additionalProperties"] is True


@pytest.mark.asyncio
async def test_mounted_transport_lists_and_executes_tools_on_both_documented_urls(monkeypatch):
    @asynccontextmanager
    async def no_services(_app):
        yield

    health = AsyncMock(return_value={"status": "healthy", "broker_connected": False, "trading_mode": "research"})
    version = AsyncMock(return_value={"version": "v-transport"})
    security = AsyncMock(return_value={"symbol": "should-not-run"})
    monkeypatch.setattr(app_module, "_sentinel_lifespan", no_services)
    monkeypatch.setattr(server.system_api, "health", health)
    monkeypatch.setattr(server.system_api, "version", version)
    monkeypatch.setattr(server.securities_api, "get_security", security)

    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://sentinel.test",
            follow_redirects=False,
        ) as http_client:
            for url in ("http://sentinel.test/mcp", "http://sentinel.test/mcp/"):
                async with Client(streamable_http_client(url, http_client=http_client)) as client:
                    listed = await client.list_tools()
                    called = await client.call_tool("sentinel_status", {})
                    invalid = await client.call_tool("security_get", {})

                assert {tool.name for tool in listed.tools} == EXPECTED_TOOLS
                assert called.is_error is False
                assert called.structured_content == {
                    "status": "healthy",
                    "broker_connected": False,
                    "trading_mode": "research",
                    "version": "v-transport",
                }
                assert invalid.is_error is True

    assert health.await_count == 2
    assert version.await_count == 2
    security.assert_not_awaited()
