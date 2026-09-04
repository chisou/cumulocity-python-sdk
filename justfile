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

docs-serve port='8000':
    uv run --with-requirements docs/requirements.txt mkdocs serve -a 127.0.0.1:{{port}}
