default:
    @just --list

bootstrap:
    uv sync --all-extras

test scope='tests':
    uv run pytest -W ignore::DeprecationWarning {{scope}}

integration-test scope='integration_tests':
    uv run pytest -W ignore::DeprecationWarning {{scope}}

lint scope='src/pyc8y tests integration_tests':
    uv run ruff check {{scope}}

format scope='src/pyc8y tests integration_tests':
    uv run ruff format {{scope}}

build:
    uv build

docs:
    uv run --with-requirements docs/requirements.txt mkdocs build

docs-serve:
    uv run --with-requirements docs/requirements.txt mkdocs serve
