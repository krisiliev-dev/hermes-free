<p align="center">
  <img src="assets/banner.png" alt="Hermes Agent" width="100%">
</p>

# Hermes Agent ☤ (Autonomous & Self-Improving)

<p align="center">
  <a href="https://github.com/krisiliev-dev/hermes-free/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://github.com/krisiliev-dev/hermes-free"><img src="https://img.shields.io/badge/Repository-hermes--free-blue?style=for-the-badge" alt="Repository"></a>
</p>

**This is a customized, self-improving version of the Hermes AI Agent, designed for maximum autonomy and reliability.** It features integrated rate limit handling, dynamic model rating, and a continuous self-improvement loop to optimize performance and discover new free models.

---

## ✨ Key Autonomous Features

This repository includes the following integrated systems that work seamlessly to make Hermes more robust:

1.  **🛡️ Core Rate Limit Protection**: Automatically intercepts all LLM (Large Language Model) calls, detects HTTP 429 (Too Many Requests) responses, extracts `Retry-After` cooldowns, and manages a thread-safe cooldown tracker. Models on cooldown are gracefully skipped, ensuring uninterrupted operation.
    *   **File**: `agent/rate_limit_wrapper.py`
    *   **Integration**: Integrated directly into `agent_init.py` for automatic startup.

2.  **📊 Dynamic Model Rater**: Intercepts model responses to evaluate and score them based on various metrics:
    *   **Quickness**: Latency of responses.
    *   **Success Rate**: How often a model provides a valid, usable response.
    *   **Qualitative Score**: (Future/Optional - requires a critic LLM) Subjective assessment of helpfulness, logic, and relevance.
    *   **File**: `agent/model_rater.py`
    *   **Integration**: Integrated directly into `agent_init.py`, wrapping the LLM calls to capture performance data.

3.  **🤖 Autonomous Improvement System**: A background daemon thread that continuously monitors Hermes's performance and system state:
    *   **Fallback Chain Optimization**: Periodically analyzes model ratings from `model_rater.py` to intelligently reorder the `fallback_providers` in `config.yaml`, promoting best-performing and available models.
    *   **New Model Discovery**: Periodically performs web searches (e.g., on OpenRouter.ai) to find new free models and integrates promising candidates into the `fallback_providers` list for evaluation.
    *   **File**: `agent/auto_improve.py`
    *   **Integration**: Integrated directly into `agent_init.py` for automatic startup as a background thread.

4.  **🔔 External Rate Limit Monitor (macOS/Windows)**: A standalone script that runs concurrently to monitor Hermes logs for rate limit events, updates a shared cooldown state, and provides desktop notifications.
    *   **File**: `Desktop/rate_limit_monitor_external.py` (located on your desktop, not in the repo's `agent/` folder by default)
    *   **Integration**: Configured via macOS LaunchAgent or Windows Task Scheduler for automatic startup.

---

## 🚀 Setup & Installation

To replicate this autonomous Hermes Agent on a new machine (macOS or Windows), follow these steps:

### Prerequisites

*   **Hermes Agent Installation**: Ensure you have a standard Hermes Agent installation on your target machine. Follow the official Hermes Agent Quick Install guide if you haven't already:
    *   **Linux, macOS, WSL2, Termux**: 
        ```bash
        curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
        ```
    *   **Windows (native, PowerShell)**:
        ```powershell
        iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)
        ```
*   **Git**: Ensure Git is installed and configured.
*   **Python 3.11+**: Hermes requires Python 3.11 or newer.

### Step 1: Clone Your Customized Repository

First, clone this `hermes-free` repository to your new machine.
Navigate to where you want to clone it (e.g., your home directory `~/` or `C:\Users\<YourUser>\`):

```bash
git clone https://github.com/krisiliev-dev/hermes-free.git
cd hermes-free
```

### Step 2: Copy Modified and New Files

You need to copy the modified core file and the new autonomous system modules into your Hermes Agent installation directory.

**Determine your Hermes Agent Installation Path:**
*   **macOS/Linux/WSL2**: `~/.hermes/hermes-agent/`
*   **Windows (native)**: `%LOCALAPPDATA%\hermes\hermes-agent\` (e.g., `C:\Users\<YourUser>\AppData\Local\hermes\hermes-agent\`)

**Copy Commands (adjust paths for your OS):**

```bash
# Assuming you are in the cloned 'hermes-free' directory
# and TARGET_HERMES_DIR is your Hermes Agent installation path

# Example for macOS/Linux:
TARGET_HERMES_DIR=~/.hermes/hermes-agent/

# Example for Windows PowerShell (run as administrator for AppData, or adjust for user-only path):
# $TARGET_HERMES_DIR="$env:LOCALAPPDATA\hermes\hermes-agent\"

# Copy modified agent_init.py
cp agent/agent_init.py "$TARGET_HERMES_DIR/agent/agent_init.py"

# Copy new autonomous system modules
cp agent/rate_limit_wrapper.py "$TARGET_HERMES_DIR/agent/rate_limit_wrapper.py"
cp agent/model_rater.py "$TARGET_HERMES_DIR/agent/model_rater.py"
cp agent/auto_improve.py "$TARGET_HERMES_DIR/agent/auto_improve.py"
```

### Step 3: Configure External Rate Limit Monitor for Auto-Start

The `rate_limit_monitor_external.py` script provides concurrent monitoring and desktop notifications. It needs to be started automatically.

#### 🍎 macOS Setup (LaunchAgent)

1.  **Copy the external monitor script** to your Desktop (or any persistent location):
    ```bash
    cp agent/rate_limit_monitor_external.py ~/Desktop/rate_limit_monitor_external.py
    chmod +x ~/Desktop/rate_limit_monitor_external.py
    ```
    *(Note: The script in this repo is a placeholder for the one I previously generated and saved to your Desktop. Ensure you use the one that was on your Desktop previously.)*

2.  **Ensure the `com.hermes.ratelimitmonitor.plist` is in place** (it was created and loaded in a previous step on your Mac). If setting up on a *new* macOS machine, you'd create it:
    ```xml
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.hermes.ratelimitmonitor</string>
        <key>ProgramArguments</key>
        <array>
            <string>/usr/bin/python3</string>
            <string>/Users/kristiyaniliev/Desktop/rate_limit_monitor_external.py</string>
            <string>--daemon</string>
            <string>--notify</string>
        </array>
        <key>RunAtLoad</key>
        <true/>
        <key>KeepAlive</key>
        <true/>
        <key>StandardOutPath</key>
        <string>/Users/kristiyaniliev/.hermes/logs/rate_limit_monitor.log</string>
        <key>StandardErrorPath</key>
        <string>/Users/kristiyaniliev/.hermes/logs/rate_limit_monitor.log</string>
        <key>ServiceDescription</key>
        <string>Hermes Agent External Rate Limit Monitor</string>
    </dict>
    </plist>
    ```
    Save this content to `~/Library/LaunchAgents/com.hermes.ratelimitmonitor.plist`.

3.  **Load the LaunchAgent**:
    ```bash
    launchctl load -w ~/Library/LaunchAgents/com.hermes.ratelimitmonitor.plist
    ```
    This command registers the service. It will start automatically after the next login/restart.

#### 🪟 Windows Setup (Task Scheduler)

1.  **Copy the external monitor script** to a persistent location, e.g., `C:\Users\<YourUser>\hermes_scripts\rate_limit_monitor_external.py`.
    *(Note: The script in this repo is a placeholder for the one I previously generated and saved to your Desktop. Ensure you use the one that was on your Desktop previously.)*

2.  **Open Task Scheduler**: Search for "Task Scheduler" in the Windows Start menu.

3.  **Create a New Task**:
    *   In the "Actions" pane, click "Create Task...".
    *   **General Tab**:
        *   **Name**: `Hermes Rate Limit Monitor`
        *   **Description**: `Starts the Hermes Agent external rate limit monitor at user logon.`
        *   Select "Run whether user is logged on or not" (for background operation)
        *   Check "Run with highest privileges"
        *   Configure for: "Windows 10" (or your specific Windows version)
    *   **Triggers Tab**:
        *   Click "New...".
        *   **Begin the task**: "At log on"
        *   "Delay task for": `30 seconds` (optional, gives system time to boot)
        *   Ensure "Enabled" is checked.
    *   **Actions Tab**:
        *   Click "New...".
        *   **Action**: "Start a program"
        *   **Program/script**: `C:\Python311\python.exe` (or wherever your Python 3.11+ executable is located)
        *   **Add arguments (optional)**: `C:\Users\<YourUser>\hermes_scripts\rate_limit_monitor_external.py --daemon --notify` (adjust path to script)
        *   **Start in (optional)**: `C:\Users\<YourUser>\hermes_scripts\` (path to script directory)
    *   **Conditions Tab**: (Optional, adjust as needed)
        *   Uncheck "Start the task only if the computer is on AC power" if you want it to run on battery.
    *   **Settings Tab**: (Optional, adjust as needed)
        *   "Allow task to be run on demand"
        *   "Stop the task if it runs longer than": (e.g., 1 day, or leave unchecked if it's a persistent daemon)
        *   "If the running task does not end when requested, force it to stop"

4.  **Save the Task**: Click "OK" and enter your Windows password if prompted. The task will now run automatically on user logon.

---

## ✅ Verification & Monitoring

Once Hermes and the external monitor are set up on your machine:

1.  **Start Hermes**: `hermes chat`
2.  **Observe Startup Messages**: You should see messages indicating `🛡️ Rate limit protection: ACTIVE`, `📊 Model Rater: ACTIVE`, and `🤖 Autonomous Improvement: ACTIVE`.
3.  **Check External Monitor Log (macOS)**: `cat ~/.hermes/logs/rate_limit_monitor.log`
4.  **Check External Monitor Status (macOS)**: `launchctl list | grep hermes` (you should see `com.hermes.ratelimitmonitor`)
5.  **Check External Monitor Status (Windows)**: Open Task Scheduler, navigate to "Task Scheduler Library", and find "Hermes Rate Limit Monitor". Check its "Last Run Result".
6.  **Monitor `config.yaml`**: The `fallback_providers` list in `~/.hermes/config.yaml` will be automatically updated by the `auto_improve.py` system based on model performance and discovery.
7.  **Check `~/.hermes/logs/hermes.log`**: For detailed activity of all autonomous systems.

This complete setup ensures your Hermes Agent is not only powerful but also self-aware and self-optimizing across different operating systems.
