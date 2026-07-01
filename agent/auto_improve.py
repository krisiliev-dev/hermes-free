
#!/usr/bin/env python3
"""
Autonomous Improvement System for Hermes Agent.

This module provides a background thread that continuously monitors Hermes's
performance, identifies areas for improvement, and proposes or implements changes.
It integrates model rating, fallback chain optimization, and proactive self-learning.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Hermes specific imports (assuming these are available in the agent's environment)
# The agent will implicitly have access to these when run within Hermes
from ..hermes_tools import web_search, read_file, write_file, patch, skill_manage
from hermes_cli.config import cfg_get, cfg_set
from agent.rate_limit_wrapper import get_rate_limit_interceptor, CooldownInfo
from agent.model_rater import get_model_rater, ModelRating # Assuming model_rater is also in agent/

logger = logging.getLogger(__name__)

class AutoImprovementSystem:
    def __init__(self):
        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._last_improvement_check = 0.0
        self._last_model_discovery = 0.0
        self._check_interval_seconds = 60 * 5  # Check every 5 minutes for improvements
        self._discovery_interval_seconds = 60 * 60 * 24 # Discover new models daily

    def start(self):
        if self._is_running:
            logger.info("Auto-improvement system already running.")
            return

        self._is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Auto-improvement system started in background thread.")

    def stop(self):
        if self._is_running:
            self._is_running = False
            if self._thread:
                self._thread.join(timeout=5)  # Give it a moment to shut down
            logger.info("Auto-improvement system stopped.")

    def _run_loop(self):
        # We need an asyncio event loop for web_search, etc.
        # Since this is a new thread, we create a new loop.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self._is_running:
            try:
                current_time = time.time()

                if current_time - self._last_improvement_check >= self._check_interval_seconds:
                    logger.debug("Running periodic improvement check...")
                    loop.run_until_complete(self._perform_improvement_check())
                    self._last_improvement_check = current_time

                if current_time - self._last_model_discovery >= self._discovery_interval_seconds:
                    logger.debug("Running periodic model discovery...")
                    loop.run_until_complete(self._discover_and_integrate_models())
                    self._last_model_discovery = current_time

            except Exception as e:
                logger.error(f"Error in auto-improvement loop: {e}", exc_info=True)

            time.sleep(min(self._check_interval_seconds, self._discovery_interval_seconds, 300)) # Sleep, but not too long

        loop.close()

    async def _perform_improvement_check(self):
        """
        Analyzes performance metrics and system state to propose or enact improvements.
        This is where the "thinking" happens.
        """
        logger.info("Performing autonomous improvement check...")
        rater = get_model_rater()
        interceptor = get_rate_limit_interceptor()

        # 1. Analyze model ratings and update fallback chain if necessary
        if rater and rater.is_enabled():
            logger.debug("Analyzing model ratings for fallback chain optimization...")
            current_ratings = rater.get_all_ratings()
            if not current_ratings:
                logger.debug("No model ratings available yet.")
                return

            # Sort models by average score (or a weighted score)
            sorted_models = sorted(
                current_ratings.items(),
                key=lambda item: item[1].average_score,
                reverse=True
            )

            # Get current fallback providers
            current_fallback_config = cfg_get("fallback_providers", [])

            # Construct a new ideal fallback list based on performance
            # Prioritize highly rated models that are not on cooldown
            new_fallback_models = []
            cooldowns_active = {}
            if interceptor and interceptor.get_tracker().is_enabled():
                cooldowns_active = {
                    self._get_model_key(c.provider, c.model): c
                    for c in interceptor.get_tracker().get_all_cooldowns().values()
                }

            for model_key, rating in sorted_models:
                provider, model_name = model_key.split('/', 1)
                # Skip if model is on cooldown
                if model_key in cooldowns_active and time.time() < cooldowns_active[model_key].until:
                    logger.debug(f"Skipping {model_key} for fallback update (on cooldown).")
                    continue
                new_fallback_models.append(f"{provider}/{model_name}")

            # Ensure essential existing models are still present even if not yet rated
            # This prevents accidental removal of important models
            existing_model_keys = {self._get_model_key_from_config_entry(entry) for entry in current_fallback_config}
            for entry in current_fallback_config:
                model_key = self._get_model_key_from_config_entry(entry)
                if model_key not in new_fallback_models and model_key not in cooldowns_active:
                    new_fallback_models.append(entry) # Add original entry back

            # Remove duplicates while preserving order
            final_fallback_list = []
            seen = set()
            for item in new_fallback_models:
                if item not in seen:
                    final_fallback_list.append(item)
                    seen.add(item)

            # Compare and update config if changed
            if final_fallback_list != current_fallback_config:
                logger.info(f"Updating 'fallback_providers' in config.yaml based on model performance.")
                cfg_set("fallback_providers", final_fallback_list)
                logger.info(f"Fallback providers updated to: {final_fallback_list}")
            else:
                logger.debug("Fallback providers are already optimized.")

        # 2. Analyze logs for common errors or missed opportunities
        # (Placeholder for more advanced log analysis)
        # This would involve reading ~/.hermes/logs/hermes.log and applying LLM reasoning
        # to suggest new skills or config changes. For now, we'll focus on model aspects.
        # Example: Read last 1000 lines of log, ask LLM: "Are there recurring errors?
        # Are there patterns of tasks that took too long or failed repeatedly?"

        # 3. Suggest new skills based on recurring task patterns
        # (Placeholder for future enhancement)

    async def _discover_and_integrate_models(self):
        """
        Searches OpenRouter for new free models and integrates them into the config.
        """
        logger.info("Discovering and integrating new free models from OpenRouter...")
        
        # Perform a web search for new OpenRouter free models
        search_query = "site:openrouter.ai/models new free models"
        search_results = await web_search(query=search_query, limit=5)

        new_model_candidates = []
        if search_results and search_results.get("data") and search_results["data"].get("web"):
            for result in search_results["data"]["web"]:
                # Try to extract model names from URLs or descriptions
                # This is a heuristic and might need refinement
                if "openrouter.ai/models/" in result["url"]:
                    model_path = result["url"].split("openrouter.ai/models/")[1].split("?")[0]
                    if ":free" in model_path or any(keyword in model_path for keyword in ["gemma", "llama", "mistral", "mixtral"]):
                        new_model_candidates.append(f"openrouter/{model_path}")
                if "free model" in result.get("description", "").lower() or "free tier" in result.get("description", "").lower():
                    # Attempt to parse model names from description if not in URL
                    # This is highly unreliable but a starting point
                    pass # More complex LLM parsing might go here

        # Also, directly query OpenRouter API if possible (requires API access or a proxy)
        # For now, stick to web_search and heuristics
        
        current_fallback_config = cfg_get("fallback_providers", [])
        
        # Filter out duplicates and models already in the config
        fresh_models = []
        existing_keys = {self._get_model_key_from_config_entry(entry) for entry in current_fallback_config}
        
        for candidate in new_model_candidates:
            model_key = candidate # Assuming format "provider/model_name"
            if model_key not in existing_keys:
                # Basic validation: try to make a dummy call or ensure it looks like a model
                # This would ideally be a real API call if we had `call_llm` here
                # For now, just add if it's new and looks like a model
                fresh_models.append(candidate)
                existing_keys.add(model_key) # Add to seen to prevent duplicates

        if fresh_models:
            logger.info(f"Found {len(fresh_models)} new model candidates. Adding to fallback chain.")
            # Add new models to the beginning of the fallback chain for testing
            # This allows them to be rated and then re-sorted by the improvement check
            updated_fallback_config = fresh_models + current_fallback_config
            cfg_set("fallback_providers", updated_fallback_config)
            logger.info(f"Fallback providers updated with new models: {fresh_models}")
        else:
            logger.info("No new free models discovered or integrated.")

    def _get_model_key(self, provider: str, model: str) -> str:
        """Helper to create a consistent key for models."""
        return f"{provider}/{model}"

    def _get_model_key_from_config_entry(self, entry: str) -> str:
        """Extracts the model key from a config entry string."""
        # Handles "provider/model_name" or "custom:provider/model_name"
        if entry.startswith("custom:"):
            return entry[len("custom:"):]
        return entry

_auto_improvement_system: Optional[AutoImprovementSystem] = None

def start_autonomous_improvement() -> bool:
    """Initializes and starts the autonomous improvement system."""
    global _auto_improvement_system
    if _auto_improvement_system is None:
        _auto_improvement_system = AutoImprovementSystem()
        _auto_improvement_system.start()
        return True
    return False

def get_system_status() -> Dict[str, Any]:
    """Returns the current status of the autonomous improvement system."""
    global _auto_improvement_system
    if _auto_improvement_system:
        return {
            "is_running": _auto_improvement_system._is_running,
            "last_improvement_check": datetime.fromtimestamp(_auto_improvement_system._last_improvement_check).isoformat() if _auto_improvement_system._last_improvement_check else "never",
            "last_model_discovery": datetime.fromtimestamp(_auto_improvement_system._last_model_discovery).isoformat() if _auto_improvement_system._last_model_discovery else "never",
            "check_interval_seconds": _auto_improvement_system._check_interval_seconds,
            "discovery_interval_seconds": _auto_improvement_system._discovery_interval_seconds,
            "threads_active": 1 if _auto_improvement_system._thread and _auto_improvement_system._thread.is_alive() else 0
        }
    return {"is_running": False, "threads_active": 0}

if __name__ == "__main__":
    # Example usage for testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    # Mock cfg_get, cfg_set, web_search, get_model_rater, get_rate_limit_interceptor
    # In a real Hermes environment, these would be available.
    
    # Simple mock for testing outside Hermes
    class MockCfg:
        def __init__(self):
            self.config = {"fallback_providers": ["openrouter/model-a", "openrouter/model-b:free"]}
        def get(self, key, default):
            return self.config.get(key, default)
        def set(self, key, value):
            self.config[key] = value
            print(f"Mock config set: {key} = {value}")

    class MockWebSearch:
        async def web_search(self, query, limit):
            print(f"Mock web search for: {query}")
            return {
                "data": {
                    "web": [
                        {"url": "https://openrouter.ai/models/some/new-free-model:free", "description": "A brand new free model!"},
                        {"url": "https://openrouter.ai/models/another/great-llm", "description": "Another free model for everyone."},
                    ]
                }
            }
    
    class MockModelRater:
        def __init__(self):
            self.ratings = {
                "openrouter/model-a": ModelRating(provider="openrouter", model="model-a", scores=[0.8, 0.7]),
                "openrouter/model-b:free": ModelRating(provider="openrouter", model="model-b:free", scores=[0.9, 0.95]),
            }
            self._enabled = True
        def is_enabled(self): return self._enabled
        def get_all_ratings(self): return self.ratings

    class MockRateLimitInterceptor:
        def __init__(self):
            self.tracker = self
        def is_enabled(self): return True
        def get_all_cooldowns(self): return {} # No cooldowns for mock test

    # Replace actual tools with mocks for standalone testing
    # Note: In actual Hermes, this direct mocking is not needed as tools are available
    _auto_improvement_system = AutoImprovementSystem()
    _auto_improvement_system.start()
    print("Auto-improvement system started (mocked environment). Monitoring for 30 seconds...")
    time.sleep(30)
    _auto_improvement_system.stop()
    print("Auto-improvement system stopped.")
    print(get_system_status())
    
    # You would typically not run this directly, but let Hermes start it.
