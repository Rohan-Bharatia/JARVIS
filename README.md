# JARVIS

A local 100% offline virtual assistant.

## Requirements

- Python 3.12+ ([`.python-version`](./.python-version) pins 3.14 for local development)
- [Ollama](https://ollama.com) running locally for the LLM runtime (offline models)

## Usage

Configuration lives in `~/.config/jarvis/jarvis.toml` (see `jarvis.example.toml`).

```sh
jarvis doctor            # run system diagnostics (config, LLM, model manifest, keys)
jarvis doctor --deep     # also verify model file hashes (slow)
jarvis keys              # create or repair the Ed25519 keypair
jarvis run --prompt "hi" # stream a response to a single prompt (prompt also read from stdin)
```

- `doctor` exits 0 only when every check passes; failures exit 1.
- Model integrity is defined in the packaged `models/manifest.yaml`; `--deep` verifies
  SHA256 hashes of local model files when a manifest entry provides them.

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
