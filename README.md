
![GitHub](https://img.shields.io/github/license/chisou/cumulocity-python-sdk)
![TOML Python Version](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FCumulocity-IoT%2Fcumulocity-python-api%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/chisou/cumulocity-python-sdk)
![GitHub Release Date](https://img.shields.io/github/release-date/chisou/cumulocity-python-sdk)
![ReadTheDocs](https://img.shields.io/readthedocs/cumulocity-python-sdk)

# cumulocity-python-sdk

This project is a Python client for the Cumulocity REST API to make it easier to develop programs, scripts, device agents or microservices in Python.

See also the [documentation on _Read the Docs_](https://cumulocity-python-sdk.readthedocs.io/).


## Installation

### Prerequisites

Before installing the module (or any module for that matter) consider creating
a virtual environment for your project. This is generally preferred over 
installing modules and dependencies globally:

```shell
cd <project-root>
python3 -m venv venv
source venv/bin/activate
```

Alternatively, using _uv_:
```shell
uv venv
```

### Installation from PyPI

The recommended way is to install the lastest distribution package directly from the Python Package Index (PyPI).
You can either add _pyc8y_ as a dependency to your project using _pyproject.toml_, _requirements.txt_ or just install
it manually:

```shell
pip install pyc8y  #  when using venv/pip
uv add pyc8y       # when using uv
```

### Manual installation

Alternatively, you can clone the repository. The module sources can be used directly within your Python 3 project.
Simply copy the _src/pyc8y_ folder to your sources root and install the requirements by running the following command:

```shell
pip3 install src/pyc8y
```

If the _src_ folder is in your sources root folder all imports should work right away. Alternatively you can add
_pyc8y_ to your _PYHTONPATH_:

```shell
export PYTHONPATH=<project-root>/src/pyc8y; $PYTHONPATH
```

## Licensing

This project is licensed under the Apache 2.0 license - see <https://www.apache.org/licenses/LICENSE-2.0>

______________________

These tools are provided as-is and without warranty or support. They do not constitute part of the Cumulocity product suite. Users are free to use, fork and modify them, subject to the license agreement. While Cumulocity GmbH welcomes contributions, we cannot guarantee to include every contribution in the master project.

______________________

You can find additional information in the [Cumulocity Developer Community](https://community.cumulocity.com/).
