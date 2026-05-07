# Copilot Instructions for Sentinel

## Project Overview

Sentinel is a long-term portfolio management system designed for ARM64 devices (Arduino UNO Q / Raspberry Pi). It features:

- **Backend**: Python 3.13+ FastAPI application with ML capabilities
- **Frontend**: React-based web UI using Mantine components
- **ML Pipeline**: Machine learning ensemble for market regime detection and trading signals
- **Hardware Integration**: Arduino and LED controller support
- **Broker Integration**: TraderNet SDK for trading operations

## Architecture

```
sentinel/               # Main Python package
├── app.py             # FastAPI application entry point
├── database/          # SQLite database layer
├── jobs/              # Background job scheduler
├── led/               # Hardware LED controller
├── ml_*.py            # ML training, prediction, monitoring modules
├── portfolio.py       # Portfolio management logic
├── broker.py          # Trading broker integration
└── utils/             # Utility modules

web/                   # React frontend
├── src/               # Source files
├── dist/              # Built assets (committed)
└── package.json       # NPM dependencies

tests/                 # Pytest test suite
```

## Python Code Guidelines

### Code Style

- **Formatter**: Use `ruff format` for consistent code formatting
- **Linter**: Use `ruff check` for code quality (F, E, W, I, S, B rules enabled)
- **Type Checker**: Use `pyright` in basic mode
- **Line Length**: 120 characters maximum
- **Target Version**: Python 3.13

### Type Annotations

- The project is transitioning to full type annotation coverage
- Type checking errors are currently downgraded to warnings
- Add type annotations when working on new code
- Preserve existing type hints when modifying code

### Testing

- Use `pytest` with `pytest-asyncio` for async tests
- Test files follow `test_*.py` naming convention
- Assertions are allowed in tests (S101 ignored)
- Type narrowing assertions allowed in specific modules (backtester, ml_ensemble)

### Async Code

- Most database operations are async (using aiosqlite)
- Use `async`/`await` consistently
- FastAPI endpoints should be async when interacting with database or broker
- Background jobs use APScheduler with async support

### Error Handling

- Use specific exception types where appropriate
- Log errors with appropriate severity levels
- Preserve error context for debugging

## Frontend Guidelines

### React Components

- Use functional components with hooks
- Follow Mantine UI component library conventions
- Use `@emotion/react` and `@emotion/styled` for styling
- Icons from `@tabler/icons-react`

### State Management

- Use `@tanstack/react-query` for server state
- Use React hooks for local state
- Use `@mantine/hooks` for common patterns

### Build Process

- Use Vite for building and development
- Built files in `web/dist/` are committed to repository
- Run `npm run build` before committing frontend changes

## Development Workflow

### Pre-commit Hooks (Lefthook)

The repository uses lefthook for automated checks. All checks run in parallel:

1. **Code Formatting**: Trailing whitespace removal, end-of-file newlines
2. **Validation**: YAML, JSON, TOML syntax validation
3. **Python**: Ruff format & check, Pyright type checking
4. **Version**: Auto-generate version.py from git
5. **Frontend**: Auto-build web assets

### Running the Application

```bash
# Development with hot reload
python main.py                    # Web server only
python main.py --all              # Web server + scheduler

# Frontend development
cd web && npm run dev

# Docker
docker-compose up
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_portfolio.py

# Run with coverage
pytest --cov=sentinel
```

### Linting and Type Checking

```bash
# Format code
ruff format .

# Check and auto-fix issues
ruff check --fix .

# Type check
pyright
```

## Machine Learning Components

### ML Pipeline Structure

- `ml_trainer.py`: Model training with hyperparameter tuning
- `ml_predictor.py`: Inference and signal generation
- `ml_monitor.py`: Model performance monitoring
- `ml_retrainer.py`: Automated retraining logic
- `ml_ensemble.py`: Ensemble model coordination
- `ml_features.py`: Feature engineering
- `regime_hmm.py`: Hidden Markov Model for market regimes

### ML Best Practices

- Models are stored in `data/ml_models/`
- Use scikit-learn, XGBoost, and hmmlearn
- Feature engineering uses TA-Lib indicators
- Models are retrained automatically when drift detected

## Database

- **Engine**: SQLite with aiosqlite for async operations
- **Location**: `data/sentinel.db`
- **Schema**: Tables for portfolios, securities, trades, ML models, settings, prices, etc.
- **Patterns**: Use singleton Database instance, connection pooling

## API Endpoints

The FastAPI app provides RESTful endpoints:

- `/api/health` - Health check
- `/api/portfolios/*` - Portfolio management
- `/api/securities/*` - Security operations
- `/api/ml/*` - ML model management
- `/api/jobs/*` - Background job control
- `/api/backtest/*` - Backtesting functionality

## Hardware Integration

### LED Controller

- Controls physical LED indicators on hardware devices
- Asyncio-based color animations
- Status indicators for portfolio state

### Arduino Integration

- Serial communication with Arduino devices
- Located in `arduino-app/` directory

## Dependencies

### Python Core Dependencies

- fastapi, uvicorn - Web framework
- tradernet-sdk - Broker API
- numpy, pandas, scipy - Data science
- scikit-learn, xgboost, hmmlearn - ML
- aiosqlite - Async database
- APScheduler - Background jobs

### Development Dependencies

- pytest, pytest-asyncio - Testing
- ruff - Linting and formatting
- pyright - Type checking

### Frontend Dependencies

- react, react-dom - UI framework
- @mantine/core - Component library
- @tanstack/react-query - Data fetching
- recharts - Charting

## Common Patterns

### Singleton Services

Many core services use singleton pattern:
- Database
- Broker
- Settings
- Portfolio
- Cache

Access via class methods, not instances.

### Configuration

- Settings stored in database (Settings model)
- Environment variables in `.env` file
- Use `Settings.get()` for runtime configuration

### Logging

- Use Python's built-in `logging` module
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Configure logging level appropriately per module

## Security Considerations

- No hardcoded credentials
- Use environment variables for secrets
- Validate input data in API endpoints
- Sanitize user inputs
- Use parameterized queries for database

## Documentation

- Docstrings for modules, classes, and public functions
- Keep README.md updated with setup instructions
- API documentation auto-generated by FastAPI
- Code comments for complex algorithms only

## Git Workflow

- Feature branches from main
- Descriptive commit messages
- Pre-commit hooks run automatically
- Version automatically incremented from git tags

## Additional Notes

- The project targets ARM64 architecture (Raspberry Pi, Arduino UNO Q)
- Consider memory constraints for ML models on embedded devices
- Frontend build artifacts are committed (web/dist/)
- Use async patterns consistently throughout the codebase
