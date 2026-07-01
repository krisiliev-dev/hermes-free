
"""
Agent initialization module.

This module contains the core agent initialization logic, now enhanced with
autonomous improvement, rate limiting, and dynamic model rating capabilities.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

# Core Hermes imports
from hermes_cli.config import cfg_get
from hermes_cli.timeouts import get_provider_request_timeout
from hermes_constants import get_hermes_home
from utils import base_url_host_matches

from agent.context_compressor import ContextCompressor
from agent.iteration_budget import IterationBudget
from agent.memory_manager import StreamingContextScrubber
from agent.model_metadata import (
    MINIMUM_CONTEXT_LENGTH,
    fetch_model_metadata,
    is_local_endpoint,
    query_ollama_num_ctx
)
from agent.process_bootstrap import _install_safe_stdio
from agent.subdirectory_hints import SubdirectoryHintTracker
from agent.think_scrubber import StreamingThinkScrubber
from agent.tool_guardrails import (
    ToolCallGuardrailConfig,
    ToolCallGuardrailController,
    ToolGuardrailDecision,
)
from hermes_cli.config import cfg_get
from hermes_cli.timeouts import get_provider_request_timeout
from hermes_constants import get_hermes_home
from utils import base_url_host_matches

# Import our new autonomous systems
from agent.rate_limit_wrapper import initialize_rate_limit_protection, get_rate_limit_interceptor
from agent.model_rater import initialize_model_rater, get_model_rater
from agent.auto_improve import start_autonomous_improvement, get_system_status as get_auto_improve_status

# Global instances (initialized in init_agent)
_rate_limit_interceptor_instance: Optional[Any] = None
_model_rater_instance: Optional[Any] = None
_auto_improve_system_started: bool = False

def _ra():
    """Lazy reference to ``run_agent`` so callers can patch
    ``run_agent.OpenAI`` / ``run_agent.cleanup_vm`` / ... and have those
    patches reach this code path.
    """
    _ra()

def _normalized_custom_base_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().rstrip("/")


def _custom_provider_model_matches(agent_model: str, entry: Dict[Any, Any]) -> bool:
    """Check if a custom provider model matches the agent's model request.

    Args:
        agent_model: The model requested by the agent (e.g. ``"openai/gpt-4"``).
        entry: A dictionary representing a provider/model entry from the model catalog.

    Returns:
        True if the entry matches the agent's model request, False otherwise.
    """
    if not isinstance(entry, dict):
        return False
    provider = entry.get("provider")
    if provider is None:
        return False
    model = entry.get("model")
    if model is None:
        return False
    if agent_model == model:
        return True
    # Handle special cases for model aliases
    if provider == "openai" and model.startswith("gpt-3.5-turbo") and "-turbo" in agent_model:
        return True
    if provider == "openai" and model.startswith("gpt-4") and "-4" in agent_model:
        return True
    return False


def init_agent(
    agent: Any,  # Use Any for AIAgent to avoid circular import if AIAgent is defined later
    *,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    api_mode: Optional[str] = None,
    reasoning_config: Optional[Dict] = None,
    prefill_messages: Optional[List[Dict]] = None,
    session_id: Optional[str] = None,
    tool_progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    clarify_callback: Optional[Callable[[str, List[str]], str]] = None,
    max_tokens: Optional[int] = None,
    # reasoning_config duplicated in args, removed one occurrence
    # prefill_messages duplicated in args, removed one occurrence
    platform: str = "cli",
    skip_context_files: bool = False,
    load_soul_identity: bool = True,
    acp_command: Optional[str] = None,
    acp_args: Optional[List[str]] = None,
) -> Any:  # Use Any for AIAgent to avoid circular import
    """Initialize an agent instance.

    Args:
        agent: The agent instance to initialize.
        model: The model to use for the agent (optional, uses model default if not set).
        provider: The provider to use for the agent (optional, uses provider default if not set).
        base_url: The base URL for the agent's API requests (optional, uses base URL default if not set).
        api_key: The API key for the agent's API requests (optional, uses API key default if not set).
        api_mode: The API mode to use for the agent's API requests (optional, uses API mode default if not set).
        reasoning_config: The reasoning configuration to use for the agent (optional, uses reasoning config default if not set).
        prefill_messages: Messages to prepend to conversation history as prefilled context.
        session_id: The session ID to use for the agent.
        tool_progress_callback: Callback function for tool progress updates.
        clarify_callback: Callback function for clarification requests.
        max_tokens: Maximum tokens for model responses (optional, uses model default if not set).
        platform: The interface platform the user is on (e.g. "cli", "telegram", "discord", "whatsapp", etc.).
        skip_context_files: If True, skip auto-injection of SOUL.md, AGENTS.md, and .cursorrules.
        load_soul_identity: If True, still use ~/.hermes/SOUL.md as the primary identity even when skip_context_files=True.
        acp_command: The ACP command to use for child agents (e.g. 'copilot').
        acp_args: Arguments for the ACP command.
    """
    _install_safe_stdio()

    # Import necessary modules (they're already in the environment)
    import asyncio
    import os
    import signal
    import threading
    import time

    # Import Hermes core utilities
    from hermes_cli.config import cfg_get
    from hermes_constants import get_hermes_home
    from utils import base_url_host_matches
    from agent.context_compressor import ContextCompressor
    from agent.iteration_budget import IterationBudget
    from agent.memory_manager import StreamingContextScrubber

    # Import our autonomous systems tools
    from agent.rate_limit_wrapper import initialize_rate_limit_protection, get_rate_limit_interceptor
    from agent.model_rater import initialize_model_rater
    from agent.auto_improve import start_autonomous_improvement, get_system_status as get_auto_improve_status

    # Initialize core systems
    _install_safe_stdio()

    # Global instances that persist across calls
    global _rate_limit_interceptor_instance, _model_rater_instance, _auto_improve_system_started

    # —  —  — Rate Limit Protection —  —  — try:
        _rate_limit_interceptor_instance = initialize_rate_limit_protection()
        agent._rate_limit_protection_enabled = True
        if not agent.quiet_mode:
            print("🛡️  Rate limit protection: ACTIVE")
    except ImportError as e:
        if not agent.quiet_mode:
            print(f"⚠️  Rate limit protection: DISABLED ({e})")
        agent._rate_limit_protection_enabled = False
        _rate_limit_interceptor_instance = None

    # —  —  — Model Rater —  —  — try:
        _model_rater_instance = initialize_model_rater()
        agent._model_rater_enabled = True
        if not agent.quiet_mode:
            print("📊 Model Rater: ACTIVE")
    except ImportError as e:
        if not agent.quiet_mode:
            print(f"⚠️  Model Rater: DISABLED ({e})")
        agent._model_rater_enabled = False
        _model_rater_instance = None

    # —  —  — Apply Wrappers to agent.call_llm —  —  — original_llm_call = getattr(agent, 'call_llm', None)

    if _model_rater_instance and original_llm_call:
        agent.call_llm = _model_rater_instance.intercept(original_llm_call)
        if not agent.quiet_mode:
            print("🚀 Model Rater applied to agent.call_llm")
        original_llm_call = agent.call_llm

    if _rate_limit_interceptor_instance and original_llm_call:
        _rate_limit_interceptor_instance.intercept(original_llm_call)
        agent.call_llm = _rate_limit_interceptor_instance.call_llm_with_protection
        if not agent.quiet_mode:
            print("🛡️ Rate Limit Interceptor applied to agent.call_llm")
    elif _rate_limit_interceptor_instance and not original_llm_call:
        pass

    # —  —  — Autonomous Improvement System —  —  — if start_autonomous_improvement():
        _auto_improve_system_started = True
        if not agent.quiet_mode:
            print("🤖 Autonomous Improvement: ACTIVE")
            status = get_auto_improve_status()
            print(f"   📊 Monitoring: {status.get('threads_active', 0)} threads active")
    else:
        if not agent.quiet_mode:
            print("⚠️  Autonomous Improvement: FAILED TO START or ALREADY RUNNING")

    # Snapshot primary runtime (for potential later use)
    agent._primary_runtime = {
        "model": agent.model,
        "provider": agent.provider,
        "base_url": agent.base_url,
        "api_key": agent.api_key,
        "api_mode": agent.api_mode,
        "reasoning_config": agent.reasoning_config,
        "prefill_messages": agent.prefill_messages,
        "session_id": agent.session_id,
        "tool_progress_callback": agent.tool_progress_callback,
        "clarify_callback": agent.clarify_callback,
        "max_tokens": agent.max_tokens,
        "_start_time": agent._start_time,
        "_last_activity_ts": agent._last_activity_ts,
        "_is_conversation_starter": agent._is_conversation_starter,
        "_is_first_turn": agent._is_first_turn,
        "_turn_count": agent._turn_count,
        "_error_count": agent._error_count,
        "_warning_count": agent._warning_count,
        "_skip_reasoning": agent._skip_reasoning,
        "_throttle_until": agent._throttle_until,
        "_is_ready": agent._is_ready,
        "_is_shutting_down": agent._is_shutting_down,
        "_should_exit": agent._should_exit,
        "_exit_code": agent._exit_code,
        "_exit_message": agent._exit_message,
        "_restart_requested": agent._restart_requested,
        "_pause_requested": agent._pause_requested,
        "_resume_requested": agent._resume_requested,
        "_update_requested": agent._update_requested,
        "_log_level": agent._log_level,
        "_log_file": agent._log_file,
        "_log_rotation_size": agent._log_rotation_size,
        "_log_rotation_count": agent._log_rotation_count,
    }

    # Set agent attributes from parameters
    agent.model = model
    agent.provider = provider
    agent.base_url = base_url
    agent.api_key = api_key
    agent.api_mode = api_mode
    agent.reasoning_config = reasoning_config or {}
    agent.prefill_messages = prefill_messages or []
    agent.session_id = session_id
    agent.tool_progress_callback = tool_progress_callback
    agent.clarify_callback = clarify_callback
    agent.max_tokens = max_tokens
    agent.acp_command = acp_command
    agent.acp_args = acp_args
    agent.platform = platform
    agent.skip_context_files = skip_context_files
    agent.load_soul_identity = load_soul_identity

    return agent
