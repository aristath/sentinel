# Getting started

## Requirements

- Linux or macOS development environment
- Python 3.13 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Node.js and npm

## Python environment

From the Sentinel repository root:

```bash
uv sync --locked --extra dev
source .venv/bin/activate
```

This installs the application plus pytest, Ruff, Pyright, and PyYAML. The
optional forecasting model stack is intentionally separate; see
[Forecasting](forecasting.md).

## Start the application

```bash
source .venv/bin/activate
python main.py
```

Defaults:

- listen address: `::`
- HTTP port: `8000`
- API: `http://localhost:8000/api/`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Override the listener explicitly when needed:

```bash
python main.py --host 127.0.0.1 --port 48000
```

An alternate port is a runtime development choice. Do not change the tracked
production-compatible defaults to accommodate one workstation.

Starting `main.py` initializes the database, seeds default settings and fixed
job schedules, starts APScheduler, starts the editable task runtime, and starts
the optional LED controller when enabled.

## Frontend development

From `sentinel/web/`:

```bash
npm install
npm run dev
```

Vite listens on port `5173` and proxies `/api` to `http://localhost:8000`.
Production static assets are built with:

```bash
npm run build
```

The generated `web/dist/` tree is tracked because FastAPI serves it directly in
production. See [Frontend and Web Awesome](frontend.md).

## Initial configuration

Open Settings in the web UI or use `PUT /api/settings/{key}`. At minimum, live
broker synchronization needs `tradernet_api_key` and `tradernet_api_secret`.
Freedom24 portfolio-structure scraping additionally needs `freedom24_login` and
`freedom24_password`.

Keep `trading_mode=research` until the portfolio, market state, permissions, and
recommendations have been inspected. See [Configuration](configuration.md).

## Verification

```bash
curl --fail http://localhost:8000/api/health
curl --fail http://localhost:8000/api/version
```

The health response includes `status`, `broker_connected`, and `trading_mode`.
A healthy HTTP response does not prove broker connectivity; check the
`broker_connected` value separately.

Then run the development gates:

```bash
source .venv/bin/activate
pytest
ruff check .
pyright
cd web
npm run build
```

## Runtime data

- SQLite and backups: `data/` by default, or `$SENTINEL_DATA_DIR`
- Editable task overrides and artifacts: `~/.sentinel/` by default, or
  `$SENTINEL_HOME`
- Frontend production build: `web/dist/`

Never replace or delete database files while Sentinel is running. Use the
backup/recovery procedures in [Deployment](deployment.md).
