test:
    PYTHONPATH=. uv run claro ./src/claro

cov:
    PYTHONPATH=. uv run coverage run --source=src/claro -m claro.cli src/claro

fix:
    PYTHONPATH=. uv run ruff format ./src
    PYTHONPATH=. uv run ruff check --fix --unsafe-fixes ./src
    PYTHONPATH=. uv run ty check ./src

init:
    git config core.hooksPath .githooks

