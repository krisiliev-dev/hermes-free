#!/usr/bin/env python3
"""
Rate Limit Wrapper Plugin for Hermes Agent

This plugin intercepts all LLM calls and adds automatic cooldown handling.
It detects 429 responses, extracts cooldown duration from headers,
and maintains a thread-safe cooldown tracker.
"""

from __future__ import annotations

import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from threading import Lock
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class CooldownInfo:
    """Information about a model's cooldown status."""
    provider: str
    model: str
    until: float
    reason: str
    initial_reset: float  # When the reset was originally scheduled
    last_used: float


class RateLimitTracker:
    """Thread-safe tracker for model cooldowns."""
    
    def __init__(self):
        self._cooldowns: Dict[str, CooldownInfo] = {}
        self._lock = Lock()
        self._enabled = True
    
    def is_on_cooldown(self, provider: str, model: str) -> bool:
        """Check if a model is currently on cooldown."""
        if not self._enabled:
            return False
        
        key = self._get_key(provider, model)
        with self._lock:
            if key in self._cooldowns:
                cooldown = self._cooldowns[key]
                if time.time() < cooldown.until:
                    return True
                # Cooldown has expired, remove it
                del self._cooldowns[key]
                logger.info(f"Model {provider}/{model} cooldown expired")
        
        return False
    
    def set_cooldown(self, provider: str, model: str, duration_seconds: float, reason: str = "Rate limit") -> None:
        """Set a cooldown for a model."""
        if not self._enabled:
            return
        
        key = self._get_key(provider, model)
        until = time.time() + duration_seconds
        
        with self._lock:
            self._cooldowns[key] = CooldownInfo(
                provider=provider,
                model=model,
                until=until,
                reason=reason,
                initial_reset=until,
                last_used=time.time()
            )
        
        logger.warning(f"Model {provider}/{model} placed on cooldown for {duration_seconds}s: {reason}")
    
    def clear_cooldown(self, provider: str, model: str) -> None:
        """Clear a model's cooldown."""
        key = self._get_key(provider, model)
        with self._lock:
            if key in self._cooldowns:
                del self._cooldowns[key]
                logger.info(f"Model {provider}/{model} cooldown cleared")
    
    def get_cooldown_status(self) -> Dict[str, Any]:
        """Get the current cooldown status for all models."""
        with self._lock:
            status = []
            for key, cooldown in self._cooldowns.items():
                remaining = int(cooldown.until - time.time())
                status.append({
                    "provider": cooldown.provider,
                    "model": cooldown.model,
                    "remaining_seconds": max(0, remaining),
                    "reason": cooldown.reason,
                    "until": cooldown.until
                })
        
        return {
            "cooldowns_active": len(status),
            "cooldowns": status
        }
    
    def get_all_cooldowns(self) -> Dict[str, CooldownInfo]:
        """Get all cooldowns (for external monitoring)."""
        with self._lock:
            return dict(self._cooldowns)
    
    def check_and_refresh_cooldowns(self) -> None:
        """Check all cooldowns and remove expired ones."""
        current_time = time.time()
        with self._lock:
            expired_keys = []
            for key, cooldown in self._cooldowns.items():
                if current_time >= cooldown.until:
                    expired_keys.append(key)
                    logger.info(f"Model {cooldown.provider}/{cooldown.model} cooldown expired")
            
            for key in expired_keys:
                del self._cooldowns[key]
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the rate limit tracking."""
        self._enabled = enabled
        logger.info(f"Rate limit tracking {'enabled' if enabled else 'disabled'}")
    
    def is_enabled(self) -> bool:
        """Check if rate limit tracking is enabled."""
        return self._enabled
    
    @staticmethod
    def _get_key(provider: str, model: str) -> str:
        """Create a unique key for a provider/model pair."""
        return f"{provider}/{model}"


class RateLimitInterceptor:
    """Interceptor that wraps model calls and handles rate limits."""
    
    def __init__(self, tracker: Optional[RateLimitTracker] = None):
        self.tracker = tracker or RateLimitTracker()
        self.original_call_llm = None
        self.intercepted = False
    
    def intercept(self, original_call_llm_func) -> None:
        """Intercept the standard call_llm function."""
        if self.intercepted:
            return
        
        self.original_call_llm = original_call_llm_func
        self.intercepted = True
        
        logger.info("Rate limit interceptor activated")
    
    async def call_llm_with_protection(
        self,
        provider: str,
        model: str,
        messages: list,
        **kwargs
    ) -> Any:
        """
        Call LLM with automatic rate limit protection.
        
        This is a drop-in replacement for the standard call_llm function.
        It checks cooldowns, handles 429 responses, and retries with
        appropriate cooldown durations.
        """
        # Check if model is on cooldown
        if self.tracker.is_on_cooldown(provider, model):
            # Determine how long to wait
            cooldown_info = self.tracker.get_all_cooldowns().get(
                self.tracker._get_key(provider, model)
            )
            if cooldown_info:
                remaining = int(cooldown_info.until - time.time())
                logger.warning(f"Model {provider}/{model} on cooldown, waiting {remaining}s")
            
            # Skip this model and try the next in the fallback chain
            # This will be handled by the caller (the fallback chain)
            raise Exception(f"Model {provider}/{model} is on cooldown")
        
        # If we have an original function to call, use it
        if self.original_call_llm:
            try:
                return await self.original_call_llm(
                    provider=provider,
                    model=model,
                    messages=messages,
                    **kwargs
                )
            except Exception as e:
                # Check if this is a rate limit error
                if self._is_rate_limit_error(e):
                    # Extract cooldown duration from error or default to 5 minutes
                    duration = self._extract_cooldown_duration(e)
                    self.tracker.set_cooldown(provider, model, duration, str(e))
                    logger.warning(f"Rate limit detected for {provider}/{model}, set to {duration}s cooldown")
                    raise
                else:
                    # Not a rate limit error, re-raise
                    raise
        
        # If no original function, call directly (shouldn't happen in normal usage)
        logger.warning("No original call_llm available, proceeding without protection")
        return None
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if an error indicates a rate limit."""
        error_str = str(error).lower()
        return any(
            term in error_str
            for term in [
                "429",
                "rate limit",
                "too many requests",
                "quota exceeded",
                "error 429",
                "rate_limited",
                "rate-limit",
                "retry after"
            ]
        )
    
    def _extract_cooldown_duration(self, error: Exception) -> float:
        """Extract cooldown duration from error message or headers."""
        error_str = str(error).lower()
        
        # Look for "Retry-After" header value
        if "retry after" in error_str:
            try:
                # Try to extract a number from the error message
                import re
                match = re.search(r"retry\s+after\s+(\d+)", error_str, re.IGNORECASE)
                if match:
                    return float(match.group(1))
            except:
                pass
        
        # Default cooldown duration
        return 300  # 5 minutes by default
    
    def get_tracker(self) -> RateLimitTracker:
        """Get the rate limit tracker instance."""
        return self.tracker


# Global instance for use by the agent
_rate_limit_interceptor: Optional[RateLimitInterceptor] = None


def get_rate_limit_interceptor() -> Optional[RateLimitInterceptor]:
    """Get the global rate limit interceptor instance."""
    return _rate_limit_interceptor


def initialize_rate_limit_protection() -> RateLimitInterceptor:
    """Initialize the rate limit protection system."""
    global _rate_limit_interceptor
    _rate_limit_interceptor = RateLimitInterceptor()
    logger.info("Rate limit protection system initialized")
    return _rate_limit_interceptor


def start_rate_limit_protection() -> None:
    """Start the rate limit protection (enable it)."""
    global _rate_limit_interceptor
    if _rate_limit_interceptor:
        _rate_limit_interceptor.tracker.set_enabled(True)
        logger.info("Rate limit protection enabled")


def stop_rate_limit_protection() -> None:
    """Stop the rate limit protection (disable it)."""
    global _rate_limit_interceptor
    if _rate_limit_interceptor:
        _rate_limit_interceptor.tracker.set_enabled(False)
        logger.info("Rate limit protection disabled")


def get_cooldown_status() -> Dict[str, Any]:
    """Get the current cooldown status."""
    global _rate_limit_interceptor
    if _rate_limit_interceptor:
        return _rate_limit_interceptor.tracker.get_cooldown_status()
    return {"cooldowns_active": 0, "cooldowns": []}