"""Model Context Protocol interface for Sentinel.

The MCP server is deliberately an adapter over Sentinel's existing application
operations.  It does not maintain separate state or duplicate portfolio,
trading, scheduling, task, or research rules.
"""

from __future__ import annotations

from typing import Any, Awaitable, TypeVar

from fastapi import HTTPException
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from sentinel.api.dependencies import CommonDependencies, get_common_deps
from sentinel.api.routers import ai as ai_api
from sentinel.api.routers import backup as backup_api
from sentinel.api.routers import forecasts as forecasts_api
from sentinel.api.routers import jobs as jobs_api
from sentinel.api.routers import planner as planner_api
from sentinel.api.routers import portfolio as portfolio_api
from sentinel.api.routers import securities as securities_api
from sentinel.api.routers import settings as settings_api
from sentinel.api.routers import system as system_api
from sentinel.api.routers import tasks as tasks_api
from sentinel.api.routers import trading as trading_api
from sentinel.version import VERSION

T = TypeVar("T")


mcp = MCPServer(
    name="sentinel",
    title="Sentinel",
    description="Read and control the Sentinel portfolio management system.",
    version=VERSION,
    instructions=(
        "Use these tools to inspect and operate Sentinel. Mutating tools use the same "
        "validation, research/live mode, broker, scheduler, and task behavior as the web application."
    ),
)


async def _deps() -> CommonDependencies:
    """Return the singleton-backed dependencies used by the HTTP API."""
    return await _call(get_common_deps())


async def _call(awaitable: Awaitable[T]) -> T:
    """Expose API validation failures as concise MCP tool errors."""
    try:
        return await awaitable
    except HTTPException as exc:
        raise ToolError(str(exc.detail)) from exc
    except (ValueError, RuntimeError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
async def sentinel_status() -> dict[str, Any]:
    """Get Sentinel health, broker state, trading mode (research cannot trade; live can), and version."""
    deps = await _deps()
    health = await _call(system_api.health(deps))
    version = await _call(system_api.version())
    return {**health, **version}


@mcp.tool()
async def portfolio_get() -> dict[str, Any]:
    """Get the current portfolio positions, cash, and total value."""
    return await _call(portfolio_api.get_portfolio(await _deps()))


@mcp.tool()
async def portfolio_composition_get() -> dict[str, Any]:
    """Get local current, ideal, and post-plan allocations plus risk, return, and concentration metrics."""
    return await _call(portfolio_api.get_portfolio_composition(await _deps()))


@mcp.tool()
async def portfolio_performance_get(period: str = "1Y") -> dict[str, Any]:
    """Get portfolio P/L history and summary for 3M, 6M, 1Y, or ALL."""
    return await _call(portfolio_api.get_portfolio_pnl_history(await _deps(), period))


@mcp.tool()
async def portfolio_period_stats_get() -> dict[str, Any]:
    """Get portfolio P/L, return, benchmark return, and alpha for 1D, 1W, 1M, 3M, 6M, and 1Y."""
    return await _call(portfolio_api.get_portfolio_period_stats(await _deps()))


@mcp.tool()
async def portfolio_projection_get(
    years: int = 10,
    monthly_net_deposit_eur: float | None = None,
) -> dict[str, Any]:
    """Project value for 5, 10, 15, 20, or 25 years from historical returns and monthly deposits; not a forecast."""
    return await _call(
        portfolio_api.get_portfolio_value_projection(
            await _deps(),
            years,
            monthly_net_deposit_eur,
        )
    )


@mcp.tool()
async def securities_overview_get(
    period: str = "1Y",
    as_of: str | None = None,
    include_inactive: bool = False,
    inactive_only: bool = False,
) -> list[dict[str, Any]]:
    """Get securities with 1M/1Y/5Y/10Y prices, positions, allocations, signals, and recommendations."""
    return await _call(
        securities_api.get_unified_view(
            await _deps(),
            period,
            as_of,
            include_inactive,
            inactive_only,
        )
    )


@mcp.tool()
async def securities_list() -> list[dict[str, Any]]:
    """List all active and inactive securities in Sentinel's universe."""
    return await _call(securities_api.get_securities(await _deps()))


@mcp.tool()
async def security_get(symbol: str) -> dict[str, Any]:
    """Get one security's metadata, current position, buy/sell permissions, and AI research preference."""
    return await _call(securities_api.get_security(symbol, await _deps()))


@mcp.tool()
async def security_prices_get(symbol: str, days: int = 365) -> list[dict[str, Any]]:
    """Get validated historical prices for a security."""
    return await _call(securities_api.get_prices(symbol, days))


@mcp.tool()
async def security_prices_sync(symbol: str, days: int = 365) -> dict[str, int]:
    """Synchronize historical prices for one security from the broker."""
    return await _call(securities_api.sync_prices(symbol, days))


@mcp.tool()
async def security_add(symbol: str) -> dict[str, Any]:
    """Add or reactivate a broker symbol in Sentinel's tracked universe; does not place an order."""
    return await _call(securities_api.add_security({"symbol": symbol}, await _deps()))


@mcp.tool()
async def security_update(symbol: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Update aliases, allow_buy, allow_sell, ai_research_multiplier, or ai_research_multiplier_analysis."""
    return await _call(
        securities_api.update_security(
            symbol,
            changes,
            await _deps(),
        )
    )


@mcp.tool()
async def security_remove(symbol: str) -> dict[str, Any]:
    """Remove from Favorites and the active universe without selling; repeating may delete inactive derived data."""
    return await _call(securities_api.delete_security(symbol, await _deps(), False))


@mcp.tool()
async def portfolio_plan_get(minimum_trade_value_eur: float | None = None) -> dict[str, Any]:
    """Get current buy/sell recommendations and the twelve-month target portfolio; does not place orders."""
    return await _call(planner_api.get_recommendations(await _deps(), minimum_trade_value_eur))


@mcp.tool()
async def portfolio_alignment_get() -> dict[str, Any]:
    """Get alignment with ideal allocations, including deviation, threshold, and rebalance status."""
    return await _call(planner_api.get_rebalance_summary())


@mcp.tool()
async def trades_get(
    symbol: str | None = None,
    side: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Get paginated trades filtered by symbol, BUY/SELL side, and inclusive YYYY-MM-DD date range."""
    return await _call(
        trading_api.get_trades(
            await _deps(),
            symbol,
            side,
            start_date,
            end_date,
            limit,
            offset,
        )
    )


@mcp.tool()
async def cashflow_summary_get() -> dict[str, Any]:
    """Get EUR totals for deposits, withdrawals, dividends, taxes, fees, net deposits, and portfolio profit."""
    return await _call(trading_api.get_cashflows(await _deps()))


@mcp.tool()
async def markets_get() -> dict[str, Any]:
    """Get open/closed state for markets represented in the active universe."""
    return await _call(system_api.get_markets_status(await _deps()))


@mcp.tool()
async def exchange_rates_get() -> dict[str, Any]:
    """Get all stored exchange rates to EUR."""
    return await _call(system_api.get_exchange_rates())


@mcp.tool()
async def settings_get() -> dict[str, Any]:
    """Get all Sentinel settings with defaults applied."""
    return await _call(settings_api.get_settings(await _deps()))


@mcp.tool()
async def setting_set(key: str, value: Any) -> dict[str, str]:
    """Set one Sentinel setting by key."""
    return await _call(settings_api.set_setting(key, {"value": value}, await _deps()))


@mcp.tool()
async def strategy_settings_set(values: dict[str, Any]) -> dict[str, str]:
    """Validate and atomically replace the complete strategy-tuning group.

    Use settings_get to preserve unchanged values.
    """
    return await _call(
        settings_api.set_settings_batch(
            {"values": values},
            await _deps(),
        )
    )


@mcp.tool()
async def job_status_get() -> dict[str, Any]:
    """Get the running job, next three scheduled jobs, and recent job activity."""
    return await _call(jobs_api.get_jobs())


@mcp.tool()
async def job_schedules_get() -> dict[str, Any]:
    """Get every fixed job's schedule, market timing, and latest and next execution."""
    return await _call(jobs_api.get_job_schedules(await _deps()))


@mcp.tool()
async def job_history_get(job_type: str | None = None, limit: int = 50) -> dict[str, Any]:
    """Get recent fixed-job executions, optionally filtered by job type."""
    return await _call(jobs_api.get_job_history(await _deps(), job_type, limit))


@mcp.tool()
async def job_run(job_type: str) -> dict[str, Any]:
    """Run a registered fixed job immediately, bypassing its schedule and market-timing check."""
    return await _call(jobs_api.run_job_endpoint(job_type))


@mcp.tool()
async def job_schedule_update(job_type: str, schedule: dict[str, Any]) -> dict[str, Any]:
    """Update and reschedule a fixed job.

    market_timing: 0 any time, 1 after market close, 2 during market open,
    3 all markets closed.
    """
    return await _call(
        jobs_api.update_job_schedule(
            job_type,
            schedule,
            await _deps(),
        )
    )


@mcp.tool()
async def tasks_list() -> list[dict[str, Any]]:
    """List the task definitions that make up Sentinel's editable AI pipeline, including enabled state and schedules."""
    return await _call(tasks_api.tasks_list())


@mcp.tool()
async def task_get(task_id: str) -> dict[str, Any]:
    """Get one editable AI pipeline task's metadata and task.js source."""
    return await _call(tasks_api.task_get(task_id))


@mcp.tool()
async def task_create(name: str) -> dict[str, Any]:
    """Create a disabled, editable AI pipeline task from a name."""
    return await _call(tasks_api.tasks_create({"name": name}))


@mcp.tool()
async def task_meta_update(task_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Update an AI pipeline task's metadata.

    Accepts name, description, tags, enabled, schedule, cwd, statePath, timeout,
    and schedulePolicy.
    """
    return await _call(
        tasks_api.task_meta_save(
            task_id,
            changes,
        )
    )


@mcp.tool()
async def task_delete(task_id: str) -> dict[str, str]:
    """Delete an idle user-defined AI pipeline task or remove an idle bundled-task override."""
    await _call(tasks_api.task_delete(task_id))
    return {"status": "deleted", "task_id": task_id}


@mcp.tool()
async def task_validate(task_id: str) -> dict[str, Any]:
    """Validate an AI pipeline task's metadata, task.js syntax, and referenced files without running it."""
    return await _call(tasks_api.task_validate(task_id))


@mcp.tool()
async def task_files_list(task_id: str) -> list[dict[str, Any]]:
    """List an AI pipeline task's files with their language, size, protection, and source."""
    return await _call(tasks_api.task_files(task_id))


@mcp.tool()
async def task_file_get(task_id: str, name: str) -> dict[str, Any]:
    """Read one AI pipeline task file, including its content, language, and source."""
    return await _call(tasks_api.task_file_get(task_id, name))


@mcp.tool()
async def task_file_save(task_id: str, name: str, content: str, create: bool = False) -> dict[str, Any]:
    """Create or replace an AI pipeline task file; set create=true only for a new filename."""
    if create:
        return await _call(tasks_api.task_file_create(task_id, {"name": name, "content": content}))
    return await _call(tasks_api.task_file_save(task_id, name, {"content": content}))


@mcp.tool()
async def task_file_delete(task_id: str, name: str) -> dict[str, str]:
    """Delete a non-protected AI pipeline task file when the task has no queued or running work."""
    await _call(tasks_api.task_file_delete(task_id, name))
    return {"status": "deleted", "task_id": task_id, "name": name}


@mcp.tool()
async def task_runs_enqueue(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Queue 1-500 AI pipeline runs.

    Each item requires task; optional fields are inputs, title, dedupeKey,
    priority, and eligibleAt as a Unix timestamp.
    """
    return await _call(tasks_api.scheduler_enqueue(items))


@mcp.tool()
async def task_runs_get(task_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """List recent runs of one AI pipeline task, including status, timing, output, and errors."""
    return await _call(tasks_api.task_runs(task_id, limit))


@mcp.tool()
async def task_run_get(run_id: str) -> dict[str, Any]:
    """Get one task execution including its current output."""
    return await _call(tasks_api.task_run_get(run_id))


@mcp.tool()
async def task_run_stop(run_id: str) -> dict[str, Any]:
    """Stop one queued or running AI pipeline run by ID."""
    return await _call(tasks_api.task_run_stop(run_id))


@mcp.tool()
async def ai_status_get() -> dict[str, Any]:
    """Get AI research pipeline status, queue, staleness, and last run."""
    return await _call(ai_api.get_ai_status(await _deps()))


@mcp.tool()
async def ai_models_get() -> dict[str, Any]:
    """List model IDs available from Sentinel's configured LLM endpoint."""
    return await _call(ai_api.get_ai_models(await _deps()))


@mcp.tool()
async def ai_prompt(prompt: str, temperature: float | None = None) -> dict[str, str]:
    """Send a prompt to Sentinel's configured LLM using its inherited system prompt."""
    body: dict[str, Any] = {"prompt": prompt}
    if temperature is not None:
        body["temperature"] = temperature
    return await _call(ai_api.create_ai_prompt(body, await _deps()))


@mcp.tool()
async def ai_units_get(kind: str | None = None, stale_only: bool = False) -> dict[str, Any]:
    """List portfolio, security, and macro subjects tracked by AI research.

    Includes staleness, run status, errors, and artifacts.
    """
    return await _call(ai_api.get_ai_units(await _deps(), kind, stale_only))


@mcp.tool()
async def ai_history_get(limit: int = 50) -> dict[str, Any]:
    """Get completed and failed AI research pipeline runs."""
    return await _call(ai_api.get_ai_history(await _deps(), limit))


@mcp.tool()
async def ai_artifact_get(kind: str, unit_key: str, name: str) -> dict[str, Any]:
    """Read a generated AI research artifact listed by ai_units_get for a portfolio, security, or macro subject."""
    return await _call(ai_api.get_ai_artifact(kind, unit_key, name, await _deps()))


@mcp.tool()
async def ai_research_run(kind: str, unit_kind: str, unit_key: str) -> dict[str, Any]:
    """Queue analyze or rate research for a security or macro unit."""
    return await _call(
        ai_api.create_ai_request(
            {"kind": kind, "unit_kind": unit_kind, "unit_key": unit_key},
            await _deps(),
        )
    )


@mcp.tool()
async def forecast_status_get() -> dict[str, Any]:
    """Get forecasting configuration, service health, and recent run status."""
    return await _call(forecasts_api.get_forecast_status(await _deps()))


@mcp.tool()
async def forecast_get(symbol: str) -> dict[str, Any]:
    """Get the latest stored forecast scores, projected path, and evaluation for one security."""
    return await _call(forecasts_api.get_symbol_forecast(symbol, await _deps()))


@mcp.tool()
async def security_buy(symbol: str, quantity: int) -> dict[str, Any]:
    """Buy through Sentinel's guards; research simulates, while live may place a real order.

    Quantity is rounded down to the security's lot size.
    """
    return await _call(trading_api.buy_security(symbol, quantity))


@mcp.tool()
async def security_sell(symbol: str, quantity: int) -> dict[str, Any]:
    """Sell through Sentinel's guards; research simulates, while live may place a real order.

    Quantity is rounded down to the security's lot size.
    """
    return await _call(trading_api.sell_security(symbol, quantity))


@mcp.tool()
async def backup_status_get() -> dict[str, Any]:
    """Get R2 backup configuration state and available backups."""
    return await _call(backup_api.get_backup_status(await _deps()))


mcp_app = mcp.streamable_http_app(
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)
