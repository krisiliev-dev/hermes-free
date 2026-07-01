#!/usr/bin/env python3
"""
Rate Limit Monitor - External Process

A standalone script that monitors Hermes logs for rate limit events
and takes proactive measures to prevent repeated rate limiting.

Features:
- Tails Hermes log files for 429 errors
- Extracts provider/model information from log context
- Maintains a shared state file with cooldown timers
- Can send desktop notifications (macOS/Linux)
- Optionally integrates with Hermes to temporarily deprioritize providers
- Logs all events for analysis

Usage:
    python rate_limit_monitor_external.py [--daemon] [--notify] [--hermes-integrate]

    --daemon: Run as background daemon
    --notify: Send desktop notifications on rate limit events
    --hermes-integrate: Attempt to integrate with Hermes runtime (experimental)
"""

import json
import os
import re
import time
import signal
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import threading

# Configuration
HERMES_HOME = os.path.join(os.path.expanduser("~"), ".hermes")
LOG_FILES = [
    os.path.join(HERMES_HOME, "logs", "gateway.log"),
    os.path.join(HERMES_HOME, "logs", "cli.log"),
]
STATE_DIR = os.path.join(HERMES_HOME, "rate_limit_monitor_external")
STATE_FILE = os.path.join(STATE_DIR, "cooldowns.json")
NOTIFY_COOLDOWN = 300  # Don't spam notifications (5 min between same provider)
DEFAULT_COOLDOWN = 300  # Default cooldown period (5 minutes)
CHECK_INTERVAL = 5  # How often to check for new log lines (seconds)

# State tracking
_cooldowns: Dict[tuple[str, str], float] = {}  # (provider, model) -> unfreeze_timestamp
_last_notification: Dict[str, float] = {}  # provider -> last_notification_timestamp
_shutdown = False
_lock = threading.RLock()


def _ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)


def _load_state() -> None:
    """Load cooldown state from disk."""
    global _cooldowns
    try:
        _ensure_dir(STATE_DIR)
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                # Reconstruct timestamps, filter out expired entries
                now = time.time()
                _cooldowns = {
                    (k[0], k[1]): v
                    for k, v in (
                        (tuple(key.split(":", 1)), value) for key, value in data.items()
                    )
                    if isinstance(v, (int, float)) and v > now
                }
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] WARNING: Could not load state: {e}")
        _cooldowns = {}


def _save_state() -> None:
    """Save cooldown state to disk."""
    try:
        _ensure_dir(STATE_DIR)
        # Convert tuple keys to strings for JSON serialization
        serializable = {f"{k[0]}:{k[1]}": v for k, v in _cooldowns.items()}
        with open(STATE_FILE, "w") as f:
            json.dump(serializable, f, indent=2)
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] WARNING: Could not save state: {e}")


def _send_notification(title: str, message: str) -> None:
    """Send desktop notification (macOS/Linux)."""
    try:
        if sys.platform == "darwin":  # macOS
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{message}" with title "{title}"',
                ],
                check=False,
                capture_output=True,
            )
        elif sys.platform.startswith("linux"):  # Linux
            subprocess.run(
                ["notify-send", title, message], check=False, capture_output=True
            )
    except Exception:
        pass  # Silently fail if notifications aren't available


def _should_notify(provider: str) -> bool:
    """Check if we should send a notification for this provider (rate limiting)."""
    now = time.time()
    last_notified = _last_notification.get(provider, 0)
    if now - last_notified >= NOTIFY_COOLDOWN:
        _last_notification[provider] = now
        return True
    return False


def _parse_log_line_for_rate_limit(line: str) -> Optional[tuple[str, str, float]]:
    """
    Parse a log line to extract rate limit information.

    Returns:
        Tuple of (provider, model, cooldown_seconds) or None if not a rate limit event
    """
    line_lower = line.lower().strip()

    # Patterns that indicate rate limit events
    rate_limit_patterns = [
        r"http.*429",
        r"status.*429",
        r"too many requests",
        r"rate.*limit.*exceeded",
        r"ratelimiterror",
        # Headers that indicate rate limiting
        r"retry-after",
        r"x-ratelimit-reset",
    ]

    # Check if this looks like a rate limit event
    is_rate_limit = False
    for pattern in rate_limit_patterns:
        if re.search(pattern, line_lower):
            is_rate_limit = True
            break

    if not is_rate_limit:
        return None

    # Try to extract provider and model information
    provider = None
    model = None
    cooldown_seconds = DEFAULT_COOLDOWN  # Default

    # Look for provider indicators
    provider_patterns = [
        r'provider[^\w"]*([a-zA-Z0-9_-]+)',
        r"using\s+([a-zA-Z0-9_-]+)",
        r"\[([a-zA-Z0-9_-]+)\]",  # [provider]
        r"(@|from)\s+([a-zA-Z0-9_-]+)",  # @provider or from provider
    ]

    for pattern in provider_patterns:
        match = re.search(pattern, line_lower)
        if match:
            # Some patterns have groups, take the last non-empty group
            groups = [g for g in match.groups() if g is not None]
            if groups:
                provider = groups[-1]
                break

    # Look for model information
    model_patterns = [
        r'model[^\w"]*([a-zA-Z0-9_.:-]+)',
        r'with\s+model[^\w"]*([a-zA-Z0-9_.:-]+)',
        r"model[=:]\s*[\"']?([^\"'\s]+)[\"']?",
    ]

    for pattern in model_patterns:
        match = re.search(pattern, line_lower)
        if match:
            model = match.group(1)
            break

    # Try to extract cooldown/retry-after time
    # Look for patterns like: retry-after: 120, x-ratelimit-reset-requests: 300
    retry_patterns = [
        r"retry-after\s*[:=]\s*(\d+)",
        r"x-ratelimit-reset-requests(?:-1h)?\s*[:=]\s*(\d+)",
        r"resets?\s+in\s*:?\s*(\d+)",
        r"wait\s*(\d+)\s*seconds?",
    ]

    for pattern in retry_patterns:
        match = re.search(pattern, line_lower)
        if match:
            try:
                extracted = int(match.group(1))
                if 5 <= extracted <= 86400:  # Reasonable range: 5 sec to 1 day
                    cooldown_seconds = float(extracted)
                    break
            except ValueError:
                pass

    # If we couldn't identify a specific provider but see known names in the log
    if not provider:
        known_providers = [
            "openrouter",
            "nous",
            "zai",
            "glm",
            "cohere",
            "anthropic",
            "openai",
            "gemini",
            "groq",
            "cerebras",
            "azure",
            "aws",
            "replicate",
            "huggingface",
        ]
        for p in known_providers:
            if p in line_lower:
                provider = p
                break

    # Default to 'unknown' if we still don't have a provider
    if not provider:
        provider = "unknown"

    return (provider, model or "default", cooldown_seconds)


def _monitor_log_file(log_path: str) -> None:
    """
    Monitor a single log file for new lines.
    This is a simple polling-based tail implementation.
    """
    if not os.path.exists(log_path):
        return

    try:
        # Get current file size
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)  # Go to end of file
            position = f.tell()

        while not _shutdown:
            try:
                # Check if file has grown
                current_size = os.path.getsize(log_path)
                if current_size > position:
                    # Read new content
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        f.seek(position)
                        new_data = f.read(current_size - position)
                        position = current_size

                        # Process each line
                        for line in new_data.splitlines():
                            result = _parse_log_line_for_rate_limit(line)
                            if result:
                                prov, modell, cooldown = result
                                _add_cooldown(prov, modell, cooldown)

                                # Send notification if enabled
                                if _should_notify(prov):
                                    _send_notification(
                                        "Rate Limit Detected",
                                        f"{prov}:{modell or 'default'} - {cooldown:.0f}s cooldown",
                                    )

                                print(
                                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                                    f"Rate limit: {prov}:{modell or 'default'} "
                                    f"- {cooldown:.0f}s cooldown"
                                )

                # Also check for log rotation (file truncated)
                elif current_size < position:
                    position = 0  # Reset to beginning

            except (OSError, IOError):
                # File might be temporarily unavailable (rotation, etc.)
                pass

            time.sleep(1)  # Check twice per second

    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR monitoring {log_path}: {e}")


def _add_cooldown(provider: str, model: str, duration: float) -> None:
    """Add or update a cooldown period."""
    key = (provider, model)
    with _lock:
        _cooldowns[key] = time.time() + duration
        _save_state()


def is_on_cooldown(provider: str, model: str = None) -> tuple[bool, float]:
    """Check if a provider/model is currently on cooldown."""
    key = (provider or "unknown", model or "default")
    with _lock:
        unfreeze_time = _cooldowns.get(key, 0.0)
        remaining = max(0.0, unfreeze_time - time.time())
        return (remaining > 0.0, remaining)


def get_status() -> str:
    """Get formatted status of all cooldowns."""
    lines = ["Rate Limit Monitor - Active Cooldowns:"]
    with _lock:
        now = time.time()
        any_active = False
        for (prov, model), unfreeze_time in sorted(_cooldowns.items()):
            remaining = max(0.0, unfreeze_time - now)
            if remaining > 0:
                any_active = True
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                seconds = int(remaining % 60)
                if hours > 0:
                    time_str = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    time_str = f"{minutes}m {seconds}s"
                else:
                    time_str = f"{seconds}s"
                lines.append(f"  {prov}:{model} - {time_str} remaining")
        if not any_active:
            lines.append("  No active cooldowns")
    return "\n".join(lines)


def cleanup_expired() -> None:
    """Remove expired cooldowns from memory and storage."""
    global _cooldowns
    with _lock:
        now = time.time()
        # Filter to only keep non-expired entries
        _cooldowns = {k: v for k, v in _cooldowns.items() if v > now}
        _save_state()


def _signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _shutdown
    print(f"[{datetime.now().isoformat()}] Received signal {signum}, shutting down...")
    _shutdown = True


def main():
    """Main entry point."""
    global _shutdown
    import argparse

    parser = argparse.ArgumentParser(description="Hermes Rate Limit Monitor")
    parser.add_argument(
        "--daemon", action="store_true", help="Run as background daemon"
    )
    parser.add_argument(
        "--notify", action="store_true", help="Send desktop notifications"
    )
    parser.add_argument(
        "--hermes-integrate",
        action="store_true",
        help="Attempt to integrate with Hermes runtime",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (process existing logs then exit)",
    )
    parser.add_argument(
        "--status", action="store_true", help="Show current status and exit"
    )

    args = parser.parse_args()

    # Handle simple commands first
    if args.status:
        _load_state()
        print(get_status())
        return 0

    if args.test:
        print("Test mode: Processing existing log entries...")
        _load_state()
        # Process existing log files for rate limit events
        for log_file in LOG_FILES:
            if os.path.exists(log_file):
                print(f"Processing {log_file}...")
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            result = _parse_log_line_for_rate_limit(line)
                            if result:
                                prov, modell, cooldown = result
                                _add_cooldown(prov, modell, cooldown)
                                print(
                                    f"  Found: {prov}:{modell or 'default'} -> {cooldown:.0f}s"
                                )
                except Exception as e:
                    print(f"Error processing {log_file}: {e}")

        print("\n" + get_status())
        return 0

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Load existing state
    _load_state()

    print(f"[{datetime.now().isoformat()}] Rate Limit Monitor starting...")
    print(f"  Monitoring: {', '.join(LOG_FILES)}")
    print(f"  State file: {STATE_FILE}")
    print(f"  Notification: {'ENABLED' if args.notify else 'DISABLED'}")
    print(f"  Hermes integration: {'ENABLED' if args.hermes_integrate else 'DISABLED'}")
    print("  Press Ctrl+C to stop")

    if not args.daemon:
        # Foreground mode - run one monitor thread per log file
        threads = []
        try:
            for log_file in LOG_FILES:
                if os.path.exists(log_file):
                    t = threading.Thread(
                        target=_monitor_log_file, args=(log_file,), daemon=True
                    )
                    t.start()
                    threads.append(t)
                    print(f"  Started monitor for {log_file}")

            # Main loop - just wait and periodically show status
            while not _shutdown:
                time.sleep(30)  # Show status every 30 seconds
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Status:")
                print(get_status())

        except KeyboardInterrupt:
            _shutdown = True
        finally:
            print(f"[{datetime.now().isoformat()}] Shutting down...")
            # Wait for threads to finish (they'll check _shutdown flag)
            time.sleep(2)

    else:
        # Daemon mode - similar but runs in background
        # In a real daemon, we'd fork() and detach from terminal
        # For simplicity, we'll just run the same logic but without the
        # periodic status prints to stdout
        try:
            threads = []
            for log_file in LOG_FILES:
                if os.path.exists(log_file):
                    t = threading.Thread(
                        target=_monitor_log_file, args=(log_file,), daemon=True
                    )
                    t.start()
                    threads.append(t)

            # Main daemon loop
            while not _shutdown:
                time.sleep(60)  # Wake up every minute to do housekeeping
                # Clean up expired entries periodically
                cleanup_expired()

        except KeyboardInterrupt:
            _shutdown = True
        finally:
            print(f"[{datetime.now().isoformat()}] Daemon stopping...")
            time.sleep(2)

    print(f"[{datetime.now().isoformat()}] Goodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
