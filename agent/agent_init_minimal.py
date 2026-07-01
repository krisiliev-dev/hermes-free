# Agent initialization module
# Rate limit protection is integrated here

from __future__ import annotations
import time
from typing import Any, Callable, Dict, List, Optional

# RATE LIMIT PROTECTION INITIALIZATION
# This is now integrated into Hermes core - it starts automatically
try:
    from agent.rate_limit_wrapper import initialize_rate_limit_protection, start_rate_limit_protection
    _rate_limit_tracker = initialize_rate_limit_protection()
    start_rate_limit_protection()
    print("Rate limit protection: ACTIVE")
except ImportError as e:
    print(f"Rate limit protection: DISABLED ({e})")
    _rate_limit_tracker = None

# Rest of the agent initialization continues below...