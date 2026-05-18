# Copyright (c) 2025 Cumulocity GmbH

from __future__ import annotations

import inspect
import os

import coolname
import dotenv
from requests import request


def load_dotenv(sample_name: str | None = None):
    """Load environment variables from .env files.

    This function will look for two files within the working directory:
    A general `.env` file and a sample specific .env-{sample_name} file
    which has higher priority.
    """
    # load general .env
    dotenv.load_dotenv()
    # check and load sample .env
    if not sample_name:
        caller_file = inspect.stack()[1].filename
        sample_name = os.path.splitext(os.path.split(caller_file)[1])[0]

    sample_env = f'.env-{sample_name}'
    if os.path.exists(sample_env):
        print(f"Found custom .env extension: {sample_env}")
        with open(sample_env, 'r', encoding='UTF-8') as f:
            dotenv.load_dotenv(stream=f, override=True)


def read_webcontent(source_url, target_path):
    """Read web content to a local file."""
    response = request('get', source_url)
    if 200 <= response.status_code <= 299:
        with open(target_path, 'wt', encoding='utf-8') as file:
            file.write(response.text)
    else:
        raise RuntimeError('Unable to read web content. Unexpected response from web site: '
                           f'HTTP {response.status_code} {response.text}')


def create_random_name(n: int = 3) -> str:
    """Generate a random name."""
    return coolname.generate_slug(n)
