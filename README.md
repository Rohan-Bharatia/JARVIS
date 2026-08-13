# JARVIS

A local 100% offline agentic assistant.

## Requirements

- Python 3.12+ (`.python-version` pins 3.14 for local development)

## Setup

```sh
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

## Development

Install the dev toolchain (pytest, ruff, mypy):

```sh
pip install --group dev
```

- Lint / format: `ruff check .` and `ruff format .`
- Type check: `mypy`
- Tests: `pytest`

## License

This repository is released under the [MIT License](https://opensource.org/license/MIT).
