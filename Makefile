.PHONY: format lint lint-fix type-check check security test-coverage all help

# Format code with Black and isort
format:
	black app/ scripts/ tests/
	isort app/ scripts/ tests/

# Run linters
lint:
	flake8 app/ scripts/ tests/
	mypy app/ --ignore-missing-imports
	pydocstyle app/ scripts/ || true  # Non-blocking, shows warnings

# Auto-fix linting issues (where possible)
lint-fix:
	black app/ scripts/ tests/
	isort app/ scripts/ tests/

# Type checking only
type-check:
	mypy app/ --ignore-missing-imports

# Security checks (critical for financial applications)
security:
	bandit -r app/ scripts/ -f json -o bandit-report.json || true
	bandit -r app/ scripts/ -ll  # Show issues
	safety check --json || true
	safety check  # Show vulnerabilities

# Test coverage
test-coverage:
	coverage run -m pytest tests/
	coverage report
	coverage html

# Find dead code
dead-code:
	vulture app/ scripts/ --min-confidence 80

# Run all checks (format, lint, type-check, security)
check: lint type-check security

# Format and check everything
all: format check

# Show help
help:
	@echo "Available commands:"
	@echo "  make format        - Auto-format code with Black and isort"
	@echo "  make lint          - Run flake8, mypy, and pydocstyle"
	@echo "  make lint-fix      - Format code (auto-fix)"
	@echo "  make type-check    - Run mypy type checking"
	@echo "  make security      - Run bandit and safety (security checks)"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make dead-code     - Find unused code with vulture"
	@echo "  make check         - Run all checks (lint + type + security)"
	@echo "  make all           - Format code and run all checks"

