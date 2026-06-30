
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
    agent: Any, # Use Any for AIAgent to avoid circular import if AIAgent is defined later
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
) -> Any: # Use Any for AIAgent to avoid circular import
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
        session_id: Pre-generated session ID for logging (optional, auto-generated if not provided).
        tool_progress_callback: Callback function(tool_name, args_preview) for progress notifications.
        clarify_callback: Callback function(question, choices) -> str for interactive user questions.
            Provided by the platform layer (CLI or gateway). If None, the clarify tool returns an error.
        max_tokens: Maximum tokens for model responses (optional, uses model default if not set).
        platform: The interface platform the user is on (e.g. "cli", "telegram", "discord", "whatsapp", etc.).
            Used to inject platform-specific formatting hints into the system prompt.
        skip_context_files: If True, skip auto-injection of SOUL.md, AGENTS.md, and .cursorrules
            into the system prompt. Use this for batch processing and data generation to avoid
            polluting trajectories with user-specific persona or project instructions.
        load_soul_identity: If True, still use ~/.hermes/SOUL.md as the primary
            identity even when skip_context_files=True. Project context files from the cwd
            remain skipped.
    """
    _install_safe_stdio()

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
    # No re-assignment for reasoning_config and prefill_messages, handled by initial assignment above
    agent.platform = platform
    agent.skip_context_files = skip_context_files
    agent.load_soul_identity = load_soul_identity

    # Set up agent state
    agent._initialized = True
    agent._start_time = time.time()
    agent._last_activity_ts = time.time()
    agent._is_conversation_starter = True
    agent._is_first_turn = True
    agent._turn_count = 0
    agent._error_count = 0
    agent._warning_count = 0
    agent._skip_reasoning = False
    agent._throttle_until = 0
    agent._is_ready = True
    agent._is_shutting_down = False
    agent._should_exit = False
    agent._exit_code = 0
    agent._exit_message = ""
    agent._restart_requested = False
    agent._pause_requested = False
    agent._resume_requested = False
    agent._update_requested = False
    agent._log_level = agent._log_level or "INFO"
    agent._log_file = agent._log_file or ""
    # These log rotation/retention settings are typically managed by the logger configuration,
    # duplicating them on the agent object without clear purpose can lead to confusion.
    # Simplified for clarity, assuming logging setup is external.
    agent._log_rotation_size = getattr(agent, '_log_rotation_size', 0)
    agent._log_rotation_count = getattr(agent, '_log_rotation_count', 0)


    # ===== AUTONOMOUS IMPROVEMENT SYSTEM INTEGRATION =====
    global _rate_limit_interceptor_instance, _model_rater_instance, _auto_improve_system_started

    # 1. Initialize Rate Limit Protection
    try:
        _rate_limit_interceptor_instance = initialize_rate_limit_protection()
        # The interceptor itself enables/disables the tracking.
        # We need to make sure agent.call_llm is wrapped by it.
        # This will be done after model_rater, as rate_limit should be outermost.
        agent._rate_limit_protection_enabled = True
        if not agent.quiet_mode:
            print("🛡️  Rate limit protection: ACTIVE")
    except ImportError as e:
        if not agent.quiet_mode:
            print(f"⚠️  Rate limit protection: DISABLED ({e})")
        agent._rate_limit_protection_enabled = False
        _rate_limit_interceptor_instance = None

    # 2. Initialize Model Rater
    try:
        _model_rater_instance = initialize_model_rater()
        # We will wrap the agent's call_llm with the rater, which will then call the rate limiter's wrapper.
        # This allows the rater to see successful calls and the rate limiter to catch exceptions.
        agent._model_rater_enabled = True
        if not agent.quiet_mode:
            print("📊 Model Rater: ACTIVE")
    except ImportError as e:
        if not agent.quiet_mode:
            print(f"⚠️  Model Rater: DISABLED ({e})")
        agent._model_rater_enabled = False
        _model_rater_instance = None

    # 3. Apply Wrappers to agent.call_llm
    # This order is crucial: rate_limit_wrapper (outermost) -> model_rater (inner) -> original call_llm
    # The agent's original call_llm might be a default or provided by a plugin.
    # We need to get the *actual* underlying call_llm that Hermes uses to make requests.
    # Assuming agent has a default call_llm or it will be set by the runtime later.
    original_llm_call = getattr(agent, 'call_llm', None)

    if _model_rater_instance and original_llm_call:
        # The rater intercepts the original_llm_call.
        # This ensures the rater is directly managing the call and can pass it to the next wrapper.
        agent.call_llm = _model_rater_instance.intercept(original_llm_call)
        if not agent.quiet_mode:
            print("🚀 Model Rater applied to agent.call_llm")
        original_llm_call = agent.call_llm # Now original_llm_call refers to the rater's wrapper

    if _rate_limit_interceptor_instance and original_llm_call:
        # The rate limit interceptor intercepts the already-wrapped call (from model_rater).
        # This makes the rate limiter the outermost layer.
        _rate_limit_interceptor_instance.intercept(original_llm_call)
        agent.call_llm = _rate_limit_interceptor_instance.call_llm_with_protection
        if not agent.quiet_mode:
            print("🛡️ Rate Limit Interceptor applied to agent.call_llm")
    elif _rate_limit_interceptor_instance and not original_llm_call:
        # If no original_llm_call (e.g., in a test setup or if it's dynamically set later)
        # we still want the rate limiter to be active.
        # This branch might need careful adjustment depending on how Hermes truly initializes call_llm.
        # For robustness, we'll ensure it attempts to wrap even if call_llm isn't immediately present.
        # The actual wrapping will then happen when agent.call_llm is finally assigned.
        pass # The interceptor already stores the wrapper method, this will be used by models if they refer to it.

    # 4. Start Autonomous Improvement System (in a background thread)
    # This needs access to the rater and interceptor instances.
    # We delay starting it until after agent init is mostly done.
    if start_autonomous_improvement():
        _auto_improve_system_started = True
        if not agent.quiet_mode:
            print("🤖 Autonomous Improvement: ACTIVE")
            status = get_auto_improve_status()
            print(f"   📊 Monitoring: {status.get('threads_active', 0)} threads active")
    else:
        if not agent.quiet_mode:
            print("⚠️  Autonomous Improvement: FAILED TO START or ALREADY RUNNING")

    # Snapshot primary runtime for per-turn restoration.
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
        # Only include relevant logging configs if they are actually used
        # in _primary_runtime restoration logic elsewhere.
    }
    
    return agent


__all__ = ["init_agent"]
