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
jarvis session list      # list encrypted session history
jarvis session show <id> # decrypt and print a session
jarvis session delete <id>
```

- `doctor` exits 0 only when every check passes; failures exit 1.
- Model integrity is defined in the packaged `models/manifest.yaml`; `--deep` verifies
  SHA256 hashes of local model files when a manifest entry provides them.
- `run` streams the agent loop: the model may call registered tools (declarative
  `*.tool.md` definitions in `src/JARVIS/tools/definitions/` plus your `tools_dir`).
  Every tool call is Ed25519-signed and approved interactively when it has side
  effects or is marked `requires_approval`. A keypair is required — create it with
  `jarvis keys`. MCP servers use the stdio transport only.
- Sessions: `run` saves every conversation to `$XDG_DATA_HOME/jarvis/sessions/`
  as AES-256-GCM-encrypted files. The key is derived (HKDF-SHA256) from your
  Ed25519 keypair, so only your machine + keypair can read history; `jarvis keys --reset`
  makes old sessions unreadable. Resume a conversation with `run --session <id>`.

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
