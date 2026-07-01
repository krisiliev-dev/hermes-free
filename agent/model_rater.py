#!/usr/bin/env python3
"""
Model Rater System for Hermes Agent.

This module provides a background system that intercepts and rates LLM calls
based on various metrics such as quickness, logical consistency, and helpfulness.
It integrates with the Autonomous Improvement System to optimize the fallback chain.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from agent.model_benchmarks import TaskType, benchmark_score

# Hermes specific imports (assuming these are available in the agent's environment)
# The agent will implicitly have access to these when run within Hermes
# These will be dynamically loaded/accessed from the agent's runtime context
# from hermes_cli.config import cfg_get, cfg_set
# from agent.rate_limit_wrapper import get_rate_limit_interceptor, CooldownInfo

logger = logging.getLogger(__name__)


@dataclass
class ModelRating:
    """Stores performance metrics for a specific model."""

    provider: str
    model: str
    quickness_scores: List[float] = field(default_factory=list)  # Time in seconds
    success_rates: List[bool] = field(
        default_factory=list
    )  # True for success, False for failure
    qualitative_scores: List[float] = field(
        default_factory=list
    )  # 0.0 - 1.0 based on external evaluation (future)

    def add_score(
        self, quickness: float, success: bool, qualitative: Optional[float] = None
    ):
        self.quickness_scores.append(quickness)
        self.success_rates.append(success)
        if qualitative is not None:
            self.qualitative_scores.append(qualitative)

        # Keep scores list to a reasonable size to avoid infinite memory growth
        max_scores = 100
        if len(self.quickness_scores) > max_scores:
            self.quickness_scores = self.quickness_scores[-max_scores:]
            self.success_rates = self.success_rates[-max_scores:]
            self.qualitative_scores = self.qualitative_scores[-max_scores:]

    @property
    def average_quickness(self) -> float:
        return mean(self.quickness_scores) if self.quickness_scores else 0.0

    @property
    def overall_success_rate(self) -> float:
        return (
            sum(self.success_rates) / len(self.success_rates)
            if self.success_rates
            else 0.0
        )

    @property
    def average_qualitative_score(self) -> float:
        return mean(self.qualitative_scores) if self.qualitative_scores else 0.0

    @property
    def combined_score(self) -> float:
        """A weighted combination of metrics for overall ranking."""
        # Higher is better. Use public benchmark priors as a cold-start signal,
        # then let local success/latency/quality data dominate as observations
        # accumulate.
        score = benchmark_score(self.provider, self.model, "general") * 0.25
        score += self.overall_success_rate * 0.55
        if self.quickness_scores:
            # Invert quickness so lower time = higher score
            # Max time of 120s for normalization. Avoid division by zero if all quickness scores are 0.
            max_quickness_for_normalization = (
                120.0  # Assuming 2 minutes is a 'long' response
            )
            normalized_quickness = max(
                0.0, 1.0 - (self.average_quickness / max_quickness_for_normalization)
            )
            score += normalized_quickness * 0.20

        # Add qualitative score if available (with a lower weight initially)
        if self.qualitative_scores:
            score += self.average_qualitative_score * 0.15

        return score

    def task_score(self, task_type: str = "general") -> float:
        """Score this model for a task bucket using benchmarks + live data."""
        normalized_task = (
            task_type
            if task_type
            in {"coding", "reasoning", "general", "fast", "creative", "critic"}
            else "general"
        )
        base = (
            benchmark_score(self.provider, self.model, cast(TaskType, normalized_task))
            * 0.45
        )
        live = self.combined_score * 0.55
        return base + live


class ModelRater:
    def __init__(self):
        self._ratings: Dict[str, ModelRating] = defaultdict(
            lambda: ModelRating("", "")
        )  # Stores by "provider/model"
        self._lock = threading.Lock()
        self._enabled = False
        self.original_call_llm: Optional[Callable] = (
            None  # Will store the actual LLM call function
        )
        self.intercepted = False
        self.critic_llm_enabled = False  # Flag to enable/disable LLM-based critique

    def start(self):
        if not self._enabled:
            self._enabled = True
            logger.info("Model Rater system enabled.")

    def stop(self):
        if self._enabled:
            self._enabled = False
            logger.info("Model Rater system disabled.")

    def set_critic_llm_enabled(self, enable: bool):
        self.critic_llm_enabled = enable
        logger.info(
            f"Critic LLM for model rating: {'enabled' if enable else 'disabled'}"
        )

    def intercept(self, original_call_llm_func: Callable) -> Callable:
        """Intercepts the original call_llm function to add rating logic."""
        if self.intercepted:
            return self.call_llm_with_rating  # Already wrapped

        self.original_call_llm = original_call_llm_func
        self.intercepted = True
        logger.info("Model Rater interceptor activated.")
        return self.call_llm_with_rating

    async def call_llm_with_rating(
        self, provider: str, model: str, messages: List[Dict], **kwargs
    ) -> Any:
        """
        Wrapped LLM call that records performance metrics.
        This function should replace the standard `call_llm` in the agent.
        """
        if not self._enabled or not self.original_call_llm:
            logger.warning(
                "Model Rater not enabled or original call_llm missing, calling directly."
            )
            if self.original_call_llm:
                return await self.original_call_llm(
                    provider=provider, model=model, messages=messages, **kwargs
                )
            raise Exception("ModelRater is not properly set up to call LLMs.")

        start_time = time.time()
        success = False
        response = None
        qualitative_score: Optional[float] = None

        try:
            response = await self.original_call_llm(
                provider=provider, model=model, messages=messages, **kwargs
            )
            success = True

            # If critic LLM is enabled, perform qualitative assessment
            if self.critic_llm_enabled:
                qualitative_score = await self._critique_response(
                    messages, response, provider, model
                )

        except Exception as e:
            logger.error(f"LLM call to {provider}/{model} failed during rating: {e}")
            success = False
            raise  # Re-raise to allow error handling further up the chain
        finally:
            end_time = time.time()
            quickness = end_time - start_time
            model_key = self._get_model_key(provider, model)

            with self._lock:
                # Ensure ModelRating is properly initialized with provider and model
                if (
                    model_key not in self._ratings
                    or self._ratings[model_key].provider == ""
                ):
                    self._ratings[model_key] = ModelRating(
                        provider=provider, model=model
                    )
                self._ratings[model_key].add_score(
                    quickness, success, qualitative_score
                )
                logger.debug(
                    f"Rated {provider}/{model}: Quickness={quickness:.2f}s, Success={success}"
                )

        return response

    async def _critique_response(
        self, original_messages: List[Dict], response: Any, provider: str, model: str
    ) -> float:
        """
        Uses another LLM to provide a qualitative score for the given response.
        This is a resource-intensive operation and should be used judiciously.
        """
        logger.debug(
            f"Critiquing response from {provider}/{model} using a critic LLM..."
        )

        # Extract the assistant's response content
        assistant_response_content = ""
        if (
            hasattr(response, "choices")
            and response.choices
            and hasattr(response.choices[0], "message")
            and hasattr(response.choices[0].message, "content")
        ):
            assistant_response_content = response.choices[0].message.content
        else:
            logger.warning(
                f"Could not extract content from response for critique. Skipping qualitative rating for {provider}/{model}."
            )
            return 0.5  # Neutral score if content can't be extracted

        # Prepare the critique prompt for a critic LLM
        critique_prompt = f"""You are an AI assistant specialized in evaluating the quality of other AI models' responses. "\
                            f"Your task is to rate the helpfulness, logical consistency, and overall quality of the following AI response to a user's query. "\
                            f"Rate it on a scale from 0.0 (very poor) to 1.0 (excellent). Provide only the numerical score. "\
                            f"Original User Query: {original_messages[0]['content'] if original_messages else 'N/A'}"\
                            f"AI's Response: {assistant_response_content}"\
                            f"Your Score (0.0-1.0):"""

        # Find a suitable critic LLM - prefer a cheap, fast one not on cooldown
        # This requires accessing the fallback chain and rate limit tracker
        # Dynamic import to avoid circular dependencies and ensure config is loaded
        from hermes_cli.config import cfg_get
        from agent.rate_limit_wrapper import get_rate_limit_interceptor

        critic_candidates = cfg_get("fallback_providers", [])
        interceptor = get_rate_limit_interceptor()

        critic_model_info = None
        for entry in critic_candidates:
            p, m = self._split_model_key(entry)
            # Check if rate limiter is available and if model is on cooldown
            if (
                interceptor
                and interceptor.get_tracker().is_enabled()
                and interceptor.get_tracker().is_on_cooldown(p, m)
            ):
                continue  # Skip models on cooldown

            # Avoid using the model we are critiquing as the critic itself
            if not (p == provider and m == model):
                critic_model_info = {"provider": p, "model": m}
                break

        if not critic_model_info:
            logger.warning(
                "No suitable critic LLM found for qualitative rating. Skipping."
            )
            return 0.5  # Neutral score

        try:
            # Temporarily use the original_call_llm that was intercepted by the rater
            # to make the critique call, to avoid recursion on the rater itself
            critic_response = await self.original_call_llm(
                provider=critic_model_info["provider"],
                model=critic_model_info["model"],
                messages=[{"role": "user", "content": critique_prompt}],
                temperature=0.0,
                max_tokens=10,  # Expect a short numerical response
            )
            if (
                critic_response
                and critic_response.choices
                and critic_response.choices[0].message
            ):
                score_str = critic_response.choices[0].message.content.strip()
                try:
                    score = float(score_str)
                    if 0.0 <= score <= 1.0:
                        logger.debug(
                            f"Critic LLM scored {provider}/{model}: {score:.2f}"
                        )
                        return score
                    else:
                        logger.warning(
                            f"Critic LLM returned out-of-range score: {score_str}. Defaulting to 0.5."
                        )
                except ValueError:
                    logger.warning(
                        f"Critic LLM returned non-numeric score: '{score_str}'. Defaulting to 0.5."
                    )

        except Exception as e:
            logger.error(
                f"Error during critic LLM call for {provider}/{model} critique: {e}"
            )

        return 0.5  # Default to neutral if critique fails

    def get_all_ratings(self) -> Dict[str, ModelRating]:
        """Returns all current model ratings."""
        with self._lock:
            return dict(self._ratings)  # Return a copy

    def get_model_rating(self, provider: str, model: str) -> Optional[ModelRating]:
        """Returns rating for a specific model."""
        with self._lock:
            return self._ratings.get(self._get_model_key(provider, model))

    def reset_ratings(self):
        """Clears all stored ratings."""
        with self._lock:
            self._ratings.clear()
            logger.info("All model ratings reset.")

    def _get_model_key(self, provider: str, model: str) -> str:
        return f"{provider}/{model}"

    def _split_model_key(self, model_key: str) -> Tuple[str, str]:
        """Splits a model key into provider and model name."""
        parts = model_key.split("/", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "unknown", model_key


_model_rater: Optional[ModelRater] = None


def initialize_model_rater() -> ModelRater:
    """Initializes and returns the global ModelRater instance."""
    global _model_rater
    if _model_rater is None:
        _model_rater = ModelRater()
        _model_rater.start()
        logger.info("Model Rater initialized and started.")
    return _model_rater


def get_model_rater() -> Optional[ModelRater]:
    """Returns the global ModelRater instance."""
    return _model_rater


# Example for direct testing (won't be run by Hermes)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Mock original call_llm
    async def mock_original_call_llm(provider, model, messages, **kwargs):
        print(
            f"Mock LLM call: {provider}/{model} with messages: {messages[0]['content']}"
        )
        await asyncio.sleep(
            0.1 + (0.5 * (hash(model) % 10 / 10))
        )  # Simulate varied latency
        if "fail_me" in messages[0]["content"]:
            raise Exception("Mock LLM failure")
        return type(
            "Response",
            (object,),
            {
                "choices": [
                    type(
                        "Choice",
                        (object,),
                        {
                            "message": type(
                                "Message",
                                (object,),
                                {
                                    "content": f"Mock response from {model} for '''{messages[0]['content']}'''."
                                },
                            )
                        },
                    )
                ]
            },
        )()

    # Mock cfg_get for critic LLM lookup (simplified)
    class MockCfg:
        def get(self, key, default):
            if key == "fallback_providers":
                return ["openrouter/gemma-4-31b-it:free", "openai/gpt-3.5-turbo"]
            return default

    class MockRateLimitInterceptor:
        def __init__(self):
            self.tracker = self  # self acts as the tracker

        def is_enabled(self):
            return True

        def is_on_cooldown(self, provider, model):
            return False  # No cooldowns for this mock

        def get_all_cooldowns(self):
            return {}

    import builtins

    builtins.cfg_get = MockCfg().get  # Temporarily inject mock
    builtins.get_rate_limit_interceptor = (
        MockRateLimitInterceptor  # Temporarily inject mock function
    )

    rater = initialize_model_rater()
    rater.intercept(mock_original_call_llm)
    rater.set_critic_llm_enabled(True)  # Enable critic LLM for testing

    async def run_test():
        print("\n--- Test 1: Successful call --- ")
        try:
            response = await rater.call_llm_with_rating(
                "openrouter",
                "test-model-1",
                [{"role": "user", "content": "Hello, AI!"}],
            )
            print(f"Response: {response.choices[0].message.content}")
        except Exception as e:
            print(f"Test failed: {e}")

        print("\n--- Test 2: Failing call --- ")
        try:
            response = await rater.call_llm_with_rating(
                "openrouter", "test-model-2", [{"role": "user", "content": "fail_me"}]
            )
            print(f"Response: {response.choices[0].message.content}")
        except Exception as e:
            print(f"Test failed: {e}")

        print("\n--- Test 3: Another successful call to existing model --- ")
        try:
            response = await rater.call_llm_with_rating(
                "openrouter",
                "test-model-1",
                [{"role": "user", "content": "How are you?"}],
            )
            print(f"Response: {response.choices[0].message.content}")
        except Exception as e:
            print(f"Test failed: {e}")

        print("\n--- Current Ratings --- ")
        ratings = rater.get_all_ratings()
        for key, rating in ratings.items():
            print(f"\nModel: {key}")
            print(f"  Avg Quickness: {rating.average_quickness:.2f}s")
            print(f"  Success Rate: {rating.overall_success_rate:.2f}")
            print(f"  Avg Qualitative Score: {rating.average_qualitative_score:.2f}")
            print(f"  Combined Score: {rating.combined_score:.2f}")

    asyncio.run(run_test())

    rater.stop()
