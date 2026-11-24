# Sentinel documentation

This directory is the canonical documentation for the current Sentinel
implementation. Source code remains authoritative when a discrepancy is found;
update the relevant document in the same change that alters a contract.

## Start here

| Document | Purpose |
|---|---|
| [Getting started](getting-started.md) | Install, run, and verify a local instance |
| [Architecture](architecture.md) | Runtime boundaries and data flow |
| [Configuration](configuration.md) | Every supported setting and environment variable |
| [API reference](api/README.md) | All FastAPI operations and payload contracts |
| [Deployment and recovery](deployment.md) | Clara production service, release, rollback, and restore |
| [Testing](testing.md) | Backend, frontend, and documentation checks |

## Application behavior

| Document | Purpose |
|---|---|
| [Strategy](strategy_contrarian.md) | Destination, opportunity timing, safety, and execution |
| [Planner and deposit history](deposit_history.md) | Contribution projections used by the planner |
| [Portfolio analytics](portfolio_composition.md) | Composition, performance, and home-market comparison |
| [Universe management](universe_management.md) | Freedom24 Favorites reconciliation and deletion rules |
| [Forecasting](forecasting.md) | Optional forecasting service and planner influence |
| [Scheduler](scheduler.md) | Fixed jobs and editable-task schedules |
| [Model Context Protocol](mcp.md) | External control through the built-in MCP server |

## AI and user interface

| Document | Purpose |
|---|---|
| [AI pipeline](ai-pipeline.md) | Research units, dependencies, artifacts, and monitoring |
| [Editable tasks](tasks.md) | Folder format, overlays, execution, scheduling, and API |
| [Frontend and Web Awesome](frontend.md) | Lit/custom-element UI architecture and development rules |
| [Database](database.md) | SQLite ownership, schema groups, migrations, and backup rules |
| [Arduino LED application](hardware-led.md) | Current UNO Q soroban display and bridge health |
| [Go TUI](go-tui.md) | Separate terminal client |

## Reference material

- [TraderNet API snapshot](tradernet/README.md) is a generated copy of upstream
  documentation. It is reference material, not Sentinel's API contract.
- [Historical Clara material](clara/README.md) records old migration and
  integration contracts.
- [Plans](plans/README.md) are dated design records. Their status headers state
  whether they remain applicable.
- [Documentation history](history/README.md) contains superseded audit/update
  notes, not current instructions.

## Documentation rules

1. Current behavior belongs in the topical documents above, not in a dated plan.
2. Every API operation must appear as a method/path heading under `docs/api/`.
3. New settings must be added to `configuration.md` with their default and role.
4. New fixed jobs must be added to `scheduler.md`, `docs/api/jobs.md`, and
   `AGENTS.md`.
5. Commands must be executable from the directory stated immediately before
   them.
6. Historical instructions must be labeled historical and must not be presented
   as deployment or API guidance.
7. Run the checks in [Testing](testing.md#documentation-checks) after changing
   documentation.
