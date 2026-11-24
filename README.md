# Sentinel

Sentinel is a long-running portfolio-management service. It synchronizes a
TraderNet/Freedom24 account, maintains local portfolio history, calculates a
deterministic contrarian allocation plan, and can execute the next eligible
transaction when trading mode is `live`.

The application consists of a Python/FastAPI service, a native-custom-element
web interface built with Lit and Web Awesome, an editable AI research task runtime,
an optional time-series forecasting service, and optional Arduino UNO Q output.

## Quick start

Requirements:

- Python 3.13 or newer
- `uv`
- Node.js and npm

```bash
uv sync --locked --extra dev
source .venv/bin/activate
python main.py
```

The production-compatible default is `http://localhost:8000`. `python main.py`
starts the API, scheduler, editable task runtime, and production frontend if
`web/dist/` exists.

For frontend development, in another terminal:

```bash
cd web
npm install
npm run dev
```

Vite defaults to `http://localhost:5173` and proxies `/api` to port `8000`.
Workstation-specific ports must be supplied at runtime; they must not replace
these tracked defaults.

The optional forecasting service uses a separate environment because its model
dependencies are not part of the main lock file. See
[Forecasting](docs/forecasting.md) before enabling it.

## Documentation

[Sentinel documentation](docs/README.md) is the canonical index. Start with:

- [Getting started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [API reference](docs/api/README.md)
- [Deployment and recovery](docs/deployment.md)
- [AI pipeline](docs/ai-pipeline.md)
- [Frontend and Web Awesome](docs/frontend.md)

Contributor and automation instructions are in [AGENTS.md](AGENTS.md).

## Safety

`research` mode calculates plans without submitting broker orders. `live` mode
permits real orders. Before changing modes, verify broker credentials, market
status, price validation, trade permissions, and the generated plan.

## License

No repository-wide license file is currently present. Do not assume permission
to redistribute Sentinel or the generated third-party reference snapshots.
