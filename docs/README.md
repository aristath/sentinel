# Sentinel Documentation

This directory contains documentation for the Sentinel portfolio management system.

## User Guide

### Core Concepts

- **[Rebalance Philosophy](../AGENTS.md#rebalance-philosophy-shift)** - The "Patience, Conviction, Profits-first" approach
- **[Deterministic Contrarian Strategy](./strategy_contrarian.md)** - How Sentinel's trading strategy works

### API Reference

- **[API Routers](../sentinel/api/routers/)** - All API endpoint implementations
- **[TraderNet API](./tradernet/)** - Broker API integration details

## Architecture Documentation

### Core Components

| Document | Description |
|---|---|
| [Portfolio Composition](./portfolio_composition.md) | Portfolio analytics, breakdowns, and risk metrics |
| [Universe Management](./universe_management.md) | Security import and Freedom24 integration |
| [Deposit History](./deposit_history.md) | Cashflow analytics for rebalancing decisions |
| [Contrarian Strategy](./strategy_contrarian.md) | Deterministic trading signal generation |

### Developer Guide

- **[Agent Guide](../AGENTS.md)** - Complete developer reference
- **[Testing Guide](../AGENTS.md#testing-approach)** - How to run and write tests
- **[Code Style](../AGENTS.md#code-style)** - Linting and formatting rules

## Plans & Design Documents

Design documents in chronological order:

| Date | Document | Status |
|---|---|---|
| 2026-02-01 | [Neon Pulse TUI Design](./plans/2026-02-01-neon-pulse-tui-design.md) | Planned |
| 2026-02-01 | [Neon Pulse TUI Implementation](./plans/2026-02-01-neon-pulse-tui-implementation.md) | Planned |
| 2026-02-05 | [Planner Invested-Only Redesign](./plans/2026-02-05-planner-invested-only-redesign-design.md) | Implemented |
| 2026-02-06 | [Contrarian Cycle Strategy V1](./plans/2026-02-06-contrarian-cycle-strategy-v1.md) | Implemented |
| 2026-02-07 | [Life Kiosk Film Design](./plans/2026-02-07-life-kiosk-film-design.md) | Planned |

## External Integrations

### TraderNet API

Documentation for the TraderNet broker API integration:

- **[Authentication](./tradernet/authentication/)** - Login, API keys, session management
- **[Alerts](./tradernet/alerts_and_requests/)** - Price alerts and file requests
- **[Currencies](./tradernet/currencies_and_websocket/)** - FX rates and WebSocket feeds
- **[Python SDK](./tradernet/authentication/python-sdk.md)** - Client library usage

## Quick Links

### For New Developers

1. Start with **[AGENTS.md](../AGENTS.md)** - Complete agent guide
2. Read **[Rebalance Philosophy](../AGENTS.md#rebalance-philosophy-shift)** - Understand the trading approach
3. Explore **[Contrarian Strategy](./strategy_contrarian.md)** - How signals are generated
4. Run tests: `pytest` - See the codebase in action

### For Maintainers

- **[Code Organization](../AGENTS.md#code-organization)** - File structure and responsibilities
- **[Common Tasks](../AGENTS.md#common-tasks)** - Adding APIs, jobs, modifying strategy
- **[Critical Gotchas](../AGENTS.md#critical-gotchas)** - Known pitfalls and solutions

### For Contributors

- **[Code Style](../AGENTS.md#code-style)** - Ruff, Pyright configuration
- **[Testing Approach](../AGENTS.md#testing-approach)** - Test organization and commands
- **[Error Handling](../AGENTS.md#error-handling)** - Logging and error patterns

## Documentation Standards

### Writing New Documentation

1. **Start with Overview** - What does this component do?
2. **Key Features** - Bullet list of main capabilities
3. **Data Structures** - Classes, data models, APIs
4. **Usage Examples** - Code snippets showing common patterns
5. **Implementation Details** - How it works under the hood
6. **Testing** - Where tests are located
7. **Related Docs** - Cross-references to other documentation

### Keeping Docs Updated

- Update docs when adding new major components
- Reference actual file paths (not hypothetical)
- Include real code examples from the codebase
- Link to test files for verification
- Update AGENTS.md when changing architecture

## Maintenance Notes

### Documentation Health Checklist

- [ ] AGENTS.md reflects current file structure
- [ ] All major modules have documentation
- [ ] API endpoints are documented
- [ ] Code examples are tested/verified
- [ ] Cross-references are valid
- [ ] Design docs have status indicators

### Last Updated

- **AGENTS.md**: 2026-07-07 (Updated to reflect current codebase)
- **portfolio_composition.md**: 2026-07-07 (New)
- **universe_management.md**: 2026-07-07 (New)
- **deposit_history.md**: 2026-07-07 (New)
- **strategy_contrarian.md**: 2026-05-18 (Existing)
