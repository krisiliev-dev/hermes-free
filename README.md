1|1|<p align="center">
2|2|  <img src="assets/banner.png" alt="Hermes Agent" width="100%">
3|3|</p>
4|4|
5|5|# Hermes Agent ☤ (Autonomous & Self-Improving)
6|6|
7|7|<p align="center">
8|8|  <a href="https://github.com/krisiliev-dev/hermes-free/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
9|9|  <a href="https://github.com/krisiliev-dev/hermes-free"><img src="https://img.shields.io/badge/Repository-hermes--free-blue?style=for-the-badge" alt="Repository"></a>
10|10|</p>
11|11|
12|12|**This is a customized, self-improving version of the Hermes AI Agent, designed for maximum autonomy and reliability.** It features integrated rate limit handling, dynamic model rating, and a continuous self-improvement loop to optimize performance and discover new free models.
13|13|
14|14|---
15|15|
16|16|## ✨ Key Autonomous Features
17|17|
18|18|This repository includes the following integrated systems that work seamlessly to make Hermes more robust:
19|19|
20|20|1.  **🛡️ Core Rate Limit Protection**: Automatically intercepts all LLM (Large Language Model) calls, detects HTTP 429 (Too Many Requests) responses, extracts `Retry-After` cooldowns, and manages a thread-safe cooldown tracker. Models on cooldown are gracefully skipped, ensuring uninterrupted operation.
21|21|    *   **File**: `agent/rate_limit_wrapper.py`
22|22|    *   **Integration**: Integrated directly into `agent_init.py` for automatic startup.
23|23|
24|24|2.  **📊 Dynamic Model Rater**: Intercepts model responses to evaluate and score them based on various metrics:
25|25|    *   **Quickness**: Latency of responses.
26|26|    *   **Success Rate**: How often a model provides a valid, usable response.
27|27|    *   **Qualitative Score**: (Future/Optional - requires a critic LLM) Subjective assessment of helpfulness, logic, and relevance.
28|28|    *   **File**: `agent/model_rater.py`
29|29|    *   **Integration**: Integrated directly into `agent_init.py`, wrapping the LLM calls to capture performance data.
30|30|
31|31|3.  **🤖 Autonomous Improvement System**: A background daemon thread that continuously monitors Hermes's performance and system state:
32|32|    *   **Fallback Chain Optimization**: Periodically analyzes model ratings from `model_rater.py` to intelligently reorder the `fallback_providers` in `config.yaml`, promoting best-performing and available models.
33|33|    *   **New Model Discovery**: Periodically performs web searches (e.g., on OpenRouter.ai) to find new free models and integrates promising candidates into the `fallback_providers` list for evaluation.
34|34|    *   **File**: `agent/auto_improve.py`
35|35|    *   **Integration**: Integrated directly into `agent_init.py` for automatic startup as a background thread.
36|36|
37|37|4.  **🔔 External Rate Limit Monitor (macOS/Windows)**: A standalone script that runs concurrently to monitor Hermes logs for rate limit events, updates a shared cooldown state, and provides desktop notifications.
38|38|    *   **File**: `Desktop/rate_limit_monitor_external.py` (located on your desktop, not in the repo's `agent/` folder by default)
39|39|    *   **Integration**: Configured via macOS LaunchAgent or Windows Task Scheduler for automatic startup.
40|40|
41|41|---
42|42|
43|43|## 🚀 Setup & Installation
44|44|
45|45|To replicate this autonomous Hermes Agent on a new machine (macOS or Windows), follow these steps:
46|46|
47|47|### Prerequisites
48|48|
49|49|*   **Hermes Agent Installation**: Ensure you have a standard Hermes Agent installation on your target machine. Follow the official Hermes Agent Quick Install guide if you haven't already:
50|50|    *   **Linux, macOS, WSL2, Termux**: 
51|51|        ```bash
52|52|        curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
53|53|        ```
54|54|    *   **Windows (native, PowerShell)**:
55|55|        ```powershell
56|56|        iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)
57|57|        ```
58|58|*   **Git**: Ensure Git is installed and configured.
59|59|*   **Python 3.11+**: Hermes requires Python 3.11 or newer.
60|60|
61|61|### Step 1: Clone Your Customized Repository
62|62|
63|63|First, clone this `hermes-free` repository to your new machine.
64|64|Navigate to where you want to clone it (e.g., your home directory `~/` or `C:\Users\<YourUser>\`):
65|65|
66|66|```bash
67|67|git clone https://github.com/krisiliev-dev/hermes-free.git
68|68|cd hermes-free
69|69|```
70|70|
71|71|### Step 2: Copy Modified and New Files
72|72|
73|73|You need to copy the modified core file and the new autonomous system modules into your Hermes Agent installation directory.
74|74|
75|75|**Determine your Hermes Agent Installation Path:**
76|76|*   **macOS/Linux/WSL2**: `~/.hermes/hermes-agent/`
77|77|*   **Windows (native)**: `%LOCALAPPDATA%\hermes\hermes-agent\` (e.g., `C:\Users\<YourUser>\AppData\Local\hermes\hermes-agent\`)
78|78|
79|79|**Copy Commands (adjust paths for your OS):**
80|80|
81|81|```bash
82|82|# Assuming you are in the cloned 'hermes-free' directory
83|83|# and TARGET_HERMES_DIR is your Hermes Agent installation path
84|84|
85|85|# Example for macOS/Linux:
86|86|TARGET_HERMES_DIR=~/.hermes/hermes-agent/
87|87|
88|88|# Example for Windows PowerShell (run as administrator for AppData, or adjust for user-only path):
89|89|# $TARGET_HERMES_DIR="$env:LOCALAPPDATA\hermes\hermes-agent\"
90|90|
91|91|# Copy modified agent_init.py
92|92|cp agent/agent_init.py "$TARGET_HERMES_DIR/agent/agent_init.py"
93|93|
94|94|# Copy new autonomous system modules
95|95|cp agent/rate_limit_wrapper.py "$TARGET_HERMES_DIR/agent/rate_limit_wrapper.py"
96|96|cp agent/model_rater.py "$TARGET_HERMES_DIR/agent/model_rater.py"
97|97|cp agent/auto_improve.py "$TARGET_HERMES_DIR/agent/auto_improve.py"
98|98|```
99|99|
100|100|### Step 3: Configure External Rate Limit Monitor for Auto-Start
101|101|
102|102|The `rate_limit_monitor_external.py` script provides concurrent monitoring and desktop notifications. It needs to be started automatically.
103|103|
104|104|#### 🍎 macOS Setup (LaunchAgent)
105|105|
106|106|1.  **Copy the external monitor script** to your Desktop (or any persistent location):
107|107|    ```bash
108|108|    cp rate_limit_monitor_external.py \"$TARGET_HERMES_DIR/rate_limit_monitor_external.py\"
109|109|    chmod \+x \"$TARGET_HERMES_DIR/rate_limit_monitor_external.py\"
110|110|    ```
111|111|    *(Note: The script in this repo is a placeholder for the one I previously generated and saved to your Desktop. Ensure you use the one that was on your Desktop previously.)*
112|112|
113|113|2.  **Ensure the `com.hermes.ratelimitmonitor.plist` is in place** (it was created and loaded in a previous step on your Mac). If setting up on a *new* macOS machine, you'd create it:
114|114|    ```xml
115|115|    <?xml version="1.0" encoding="UTF-8"?>
116|116|    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
117|117|    <plist version="1.0">
118|118|    <dict>
119|119|        <key>Label</key>
120|120|        <string>com.hermes.ratelimitmonitor</string>
121|121|        <key>ProgramArguments</key>
122|122|        <array>
123|123|            <string>/usr/bin/python3</string>
124|124|            <string>/Users/kristiyaniliev/.hermes/hermes-agent/rate_limit_monitor_external.py</string>
125|125|            <string>--daemon</string>
126|126|            <string>--notify</string>
127|127|        </array>
128|128|        <key>RunAtLoad</key>
129|129|        <true/>
130|130|        <key>KeepAlive</key>
131|131|        <true/>
132|132|        <key>StandardOutPath</key>
133|133|        <string>/Users/kristiyaniliev/.hermes/logs/rate_limit_monitor.log</string>
134|134|        <key>StandardErrorPath</key>
135|135|        <string>/Users/kristiyaniliev/.hermes/logs/rate_limit_monitor.log</string>
136|136|        <key>ServiceDescription</key>
137|137|        <string>Hermes Agent External Rate Limit Monitor</string>
138|138|    </dict>
139|139|    </plist>
140|140|    ```
141|141|    Save this content to `~/Library/LaunchAgents/com.hermes.ratelimitmonitor.plist`.
142|142|
143|143|3.  **Load the LaunchAgent**:
144|144|    ```bash
145|145|    launchctl load -w ~/Library/LaunchAgents/com.hermes.ratelimitmonitor.plist
146|146|    ```
147|147|    This command registers the service. It will start automatically after the next login/restart.
148|148|
149|149|#### 🪟 Windows Setup (Task Scheduler)
150|150|
151|151|1.  **Copy the external monitor script** to a persistent location, e.g., `$TARGET_HERMES_DIR\rate_limit_monitor_external.py`.
152|152|    *(Note: The script in this repo is a placeholder for the one I previously generated and saved to your Desktop. Ensure you use the one that was on your Desktop previously.)*
153|153|
154|154|2.  **Open Task Scheduler**: Search for "Task Scheduler" in the Windows Start menu.
155|155|
156|156|3.  **Create a New Task**:
157|157|    *   In the "Actions" pane, click "Create Task...".
158|158|    *   **General Tab**:
159|159|        *   **Name**: `Hermes Rate Limit Monitor`
160|160|        *   **Description**: `Starts the Hermes Agent external rate limit monitor at user logon.`
161|161|        *   Select "Run whether user is logged on or not" (for background operation)
162|162|        *   Check "Run with highest privileges"
163|163|        *   Configure for: "Windows 10" (or your specific Windows version)
164|164|    *   **Triggers Tab**:
165|165|        *   Click "New...".
166|166|        *   **Begin the task**: "At log on"
167|167|        *   "Delay task for": `30 seconds` (optional, gives system time to boot)
168|168|        *   Ensure "Enabled" is checked.
169|169|    *   **Actions Tab**:
170|170|        *   Click "New...".
171|171|        *   **Action**: "Start a program"
172|172|        *   **Program/script**: `C:\Python311\python.exe` (or wherever your Python 3.11+ executable is located)
173|173|        *   **Add arguments (optional)**: `$TARGET_HERMES_DIR\rate_limit_monitor_external.py --daemon --notify` (adjust path to script)
174|174|        *   **Start in (optional)**: `%TARGET_HERMES_DIR%\` (path to script directory)
175|175|    *   **Conditions Tab**: (Optional, adjust as needed)
176|176|        *   Uncheck "Start the task only if the computer is on AC power" if you want it to run on battery.
177|177|    *   **Settings Tab**: (Optional, adjust as needed)
178|178|        *   "Allow task to be run on demand"
179|179|        *   "Stop the task if it runs longer than": (e.g., 1 day, or leave unchecked if it's a persistent daemon)
180|180|        *   "If the running task does not end when requested, force it to stop"
181|181|
182|182|4.  **Save the Task**: Click "OK" and enter your Windows password if prompted. The task will now run automatically on user logon.
183|183|
184|184|---
185|185|
186|186|## ✅ Verification & Monitoring
187|187|
188|188|Once Hermes and the external monitor are set up on your machine:
189|189|
190|190|1.  **Start Hermes**: `hermes chat`
191|191|2.  **Observe Startup Messages**: You should see messages indicating `🛡️ Rate limit protection: ACTIVE`, `📊 Model Rater: ACTIVE`, and `🤖 Autonomous Improvement: ACTIVE`.
192|192|3.  **Check External Monitor Log (macOS)**: `cat ~/.hermes/logs/rate_limit_monitor.log`
193|193|4.  **Check External Monitor Status (macOS)**: `launchctl list | grep hermes` (you should see `com.hermes.ratelimitmonitor`)
194|194|5.  **Check External Monitor Status (Windows)**: Open Task Scheduler, navigate to "Task Scheduler Library", and find "Hermes Rate Limit Monitor". Check its "Last Run Result".
195|195|6.  **Monitor `config.yaml`**: The `fallback_providers` list in `~/.hermes/config.yaml` will be automatically updated by the `auto_improve.py` system based on model performance and discovery.
196|196|7.  **Check `~/.hermes/logs/hermes.log`**: For detailed activity of all autonomous systems.
197|197|
198|198|This complete setup ensures your Hermes Agent is not only powerful but also self-aware and self-optimizing across different operating systems.
199|199|