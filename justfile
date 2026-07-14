# Development commands. Everything runs through uv against the locked env.

# Fast feedback: lint, typecheck, unit tests.
default: check

# Install/refresh the dev environment from the lockfile.
sync:
    uv sync --locked --all-extras --dev

# All offline gates, same as CI.
check: lint typecheck test

lint:
    uv run ruff check src/
    uv run ruff format --check src/

fmt:
    uv run ruff check src/ --fix
    uv run ruff format src/

# Error-level diagnostics fail; pre-existing warnings are the ratchet
# (see [tool.ty.rules] in pyproject.toml).
typecheck:
    uv run ty check --exit-zero-on-warning src/tusdt_cli

# Offline unit tests.
test *ARGS:
    uv run pytest {{ARGS}}

cov:
    uv run pytest --cov --cov-report=term

# Build the package (wheel + sdist).
build:
    rm -rf dist/
    uv run python -m build
