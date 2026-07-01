# Hermes Portable Patch

This repository contains minimal patches to enable a **self‑contained, portable Hermes‑free agent** with:

- Secure credential storage (via `keyring` or encrypted JSON fallback)
- Autonomous improvement system (rate‑limit wrapper, model rater, background auto‑improve)
- Optional ACP command/args for spawning child agents (e.g., Copilot)

The patches are designed to be applied onto an existing Hermes installation (the one you already have from `pip install hermes-agent` or similar). No need to reinstall Hermes—just copy the files.

## Quick Start

1. **Clone this repo**

   ```bash
   git clone https://github.com/krisiliev-dev/hermes-free.git
   cd hermes-free
   ```

2. **Run the copy script** (choose the appropriate one for your OS)

   - **macOS / Linux**

     ```bash
     ./copy_files.sh   # defaults to ~/.hermes/hermes-agent
     # or specify a custom path:
     # ./copy_files.sh /path/to/your/hermes/agent
     ```

   - **Windows PowerShell**

     ```powershell
     .\copy_files_windows.py
     ```

   The script will:
   - Copy `hermes_tools.py` to the Hermes agent root.
   - Update `agent/agent_init.py` with the autonomous‑system hooks.
   - Ensure the `hermes_cli` package is up‑to‑date (needed for `cfg_get`/`cfg_set`).

3. **(Optional) Store your API keys securely**

   The patch includes a small `config.py` module that safely stores credentials using the OS keychain (Keychain, Secret Service/KWallet, Windows Credential Manager) or an encrypted JSON file if `keyring` is unavailable.

   Example (run once per machine):

   ```bash
   python - <<PY
   from hermes_tools import set_credentials  # or from hermes_portable.config if you prefer the wrapper
   set_credentials("openrouter", "sk-your-openrouter-key")
   print("API key stored securely.")
   PY
   ```

   You can store multiple services (e.g., `openrouter`, `github`, `tavily`) the same way.

4. **Restart Hermes**

   Launch Hermes as usual:

   ```bash
   hermes chat
   ```

   You should see startup messages like:

   ```
   🛡️  Rate limit protection: ACTIVE
   📊 Model Rater: ACTIVE
   🤖 Autonomous Improvement: ACTIVE
   ```

   The agent will now use the autonomous protection stack and will fall back to free models (via OpenRouter, Nous‑Research, etc.) when a key is missing or a provider rate‑limits.

## What the patch does

- **`hermes_tools.py`** – a self‑contained drop‑in replacement for the Hermes tool SDK (`web_search`, `read_file`, `write_file`, `patch`, `skill_manage`, …). No external dependencies.
- **`agent/agent_init.py`** – modified to:
  1. Accept `acp_command` and `acp_args` arguments.
  2. Initialise the rate‑limit interceptor, model rater, and auto‑improvement background thread.
  3. Attach the wrappers to the agent’s `call_llm` method.
- **`hermes_cli/config.py`** – unchanged; used for `cfg_get`/`cfg_set` calls from `agent/auto_improve.py`.
- **Copy scripts** – automate placing the files in the correct locations.

## Customisation

- To change the default model/provider, edit the arguments when you call `hermes chat` or set environment variables (`HERMES_MODEL`, `HERMES_PROVIDER`, etc.).
- The ACP command is optional; if you don’t need child‑agent spawning, omit `acp_command`/`acp_args`.

## License

MIT – feel free to adapt and share.

Enjoy your portable, self‑improving Hermes agent! 🚀
