"""Static benchmark priors for model routing.

These priors are intentionally conservative. They are not a replacement for live
success/rate-limit data from :mod:`agent.model_rater`; they are the cold-start
signal used before Hermes has enough local observations.

Sources used when creating this table:
- SWE-bench leaderboard: https://www.swebench.com
- LiveCodeBench overview: https://livecodebench.github.io
- Nebius Qwen3-Coder/OpenHands report:
  https://nebius.com/blog/posts/openhands-trajectories-with-qwen3-coder-480b

The table favors free/open-access models likely to appear in OpenRouter/Nous
fallback chains. Exact benchmark numbers move over time, so scores are normalized
0.0-1.0 capability priors rather than copied leaderboard ranks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

TaskType = Literal["coding", "reasoning", "general", "fast", "creative", "critic"]


@dataclass(frozen=True)
class BenchmarkPrior:
    """Capability prior for a model family or exact slug."""

    pattern: str
    coding: float
    reasoning: float
    general: float
    fast: float
    creative: float
    critic: float
    notes: str

    def score(self, task_type: TaskType) -> float:
        return float(getattr(self, task_type))


# Ordered most-specific to least-specific. Matching is substring-based so this
# works across provider prefixes and OpenRouter ':free' suffixes.
BENCHMARK_PRIORS: tuple[BenchmarkPrior, ...] = (
    BenchmarkPrior(
        pattern="qwen3-coder-480b",
        coding=0.97,
        reasoning=0.88,
        general=0.84,
        fast=0.45,
        creative=0.72,
        critic=0.86,
        notes="Qwen3-Coder-480B is a strong open coding/agentic model; Nebius reports 66.5% SWE-bench Verified Pass@1 for the 480B specialist.",
    ),
    BenchmarkPrior(
        pattern="qwen3-coder",
        coding=0.94,
        reasoning=0.86,
        general=0.82,
        fast=0.55,
        creative=0.72,
        critic=0.84,
        notes="Qwen3-Coder family is specialized for software-engineering and coding-agent tasks.",
    ),
    BenchmarkPrior(
        pattern="qwen3-235b",
        coding=0.90,
        reasoning=0.88,
        general=0.86,
        fast=0.50,
        creative=0.78,
        critic=0.86,
        notes="Large Qwen3 model; Nebius RFT 235B checkpoint reports 61.7% SWE-bench Verified Pass@1.",
    ),
    BenchmarkPrior(
        pattern="qwen3-30b",
        coding=0.82,
        reasoning=0.78,
        general=0.78,
        fast=0.68,
        creative=0.72,
        critic=0.76,
        notes="Qwen3 30B is a capable open model; coding-specialized/RFT variants are stronger.",
    ),
    BenchmarkPrior(
        pattern="kimi-k2",
        coding=0.92,
        reasoning=0.88,
        general=0.86,
        fast=0.55,
        creative=0.80,
        critic=0.86,
        notes="Kimi K2 family appears high on SWE-bench style software-engineering leaderboards.",
    ),
    BenchmarkPrior(
        pattern="deepseek-v3",
        coding=0.90,
        reasoning=0.86,
        general=0.86,
        fast=0.62,
        creative=0.76,
        critic=0.84,
        notes="DeepSeek V3 family is strong for coding and general reasoning on public leaderboards.",
    ),
    BenchmarkPrior(
        pattern="deepseek-r1",
        coding=0.84,
        reasoning=0.93,
        general=0.84,
        fast=0.45,
        creative=0.72,
        critic=0.88,
        notes="DeepSeek R1 is strongest as a reasoning/checking model rather than fastest code writer.",
    ),
    BenchmarkPrior(
        pattern="glm-5",
        coding=0.89,
        reasoning=0.90,
        general=0.86,
        fast=0.56,
        creative=0.78,
        critic=0.86,
        notes="GLM high-reasoning entries rank well on SWE-bench style tasks.",
    ),
    BenchmarkPrior(
        pattern="glm-4.5",
        coding=0.86,
        reasoning=0.88,
        general=0.84,
        fast=0.58,
        creative=0.78,
        critic=0.84,
        notes="GLM 4.5 is a strong open/general reasoning model.",
    ),
    BenchmarkPrior(
        pattern="minimax-m2",
        coding=0.88,
        reasoning=0.88,
        general=0.86,
        fast=0.58,
        creative=0.82,
        critic=0.84,
        notes="MiniMax M2 appears high on SWE-bench style agentic coding leaderboards.",
    ),
    BenchmarkPrior(
        pattern="hermes-4",
        coding=0.76,
        reasoning=0.82,
        general=0.84,
        fast=0.62,
        creative=0.88,
        critic=0.80,
        notes="Nous Hermes is tuned for helpful general/creative use; not the first coding prior when Qwen/DeepSeek/Kimi are available.",
    ),
    BenchmarkPrior(
        pattern="hermes",
        coding=0.70,
        reasoning=0.78,
        general=0.82,
        fast=0.65,
        creative=0.86,
        critic=0.76,
        notes="Hermes-family general prior.",
    ),
    BenchmarkPrior(
        pattern="llama-4",
        coding=0.72,
        reasoning=0.76,
        general=0.82,
        fast=0.66,
        creative=0.80,
        critic=0.74,
        notes="Llama 4 family is useful general fallback; usually not the top code-specialist choice.",
    ),
    BenchmarkPrior(
        pattern="llama-3.3",
        coding=0.68,
        reasoning=0.72,
        general=0.78,
        fast=0.72,
        creative=0.76,
        critic=0.70,
        notes="Reliable general fallback prior.",
    ),
    BenchmarkPrior(
        pattern="mistral",
        coding=0.68,
        reasoning=0.76,
        general=0.78,
        fast=0.74,
        creative=0.76,
        critic=0.72,
        notes="LiveCodeBench observed Mistral-Large as useful for natural-language-heavy code execution/test-output tasks.",
    ),
    BenchmarkPrior(
        pattern="gemma",
        coding=0.62,
        reasoning=0.66,
        general=0.72,
        fast=0.78,
        creative=0.70,
        critic=0.64,
        notes="Good lightweight fallback; not preferred for difficult code edits.",
    ),
)

DEFAULT_PRIOR = BenchmarkPrior(
    pattern="default",
    coding=0.55,
    reasoning=0.55,
    general=0.60,
    fast=0.60,
    creative=0.60,
    critic=0.55,
    notes="Unknown model; use only after known stronger candidates or when live metrics prove it.",
)


def normalize_model_key(provider: str | None, model: str | None) -> str:
    """Return a lowercase comparable provider/model key."""
    provider = (provider or "").strip().lower()
    model = (model or "").strip().lower()
    if provider and model and not model.startswith(provider + "/"):
        return f"{provider}/{model}"
    return model or provider


def find_prior(provider: str | None, model: str | None) -> BenchmarkPrior:
    """Find the best static benchmark prior for provider/model."""
    key = normalize_model_key(provider, model)
    for prior in BENCHMARK_PRIORS:
        if prior.pattern in key:
            return prior
    return DEFAULT_PRIOR


def benchmark_score(
    provider: str | None, model: str | None, task_type: TaskType = "general"
) -> float:
    """Return normalized 0.0-1.0 benchmark prior for a task type."""
    return find_prior(provider, model).score(task_type)


def infer_task_type(text: str | None) -> TaskType:
    """Infer a routing bucket from a user/developer task description."""
    lowered = (text or "").lower()
    coding_markers = (
        "code",
        "bug",
        "lint",
        "pytest",
        "unit test",
        "compile",
        "syntax",
        "traceback",
        "repository",
        "git",
        "commit",
        "diff",
        "function",
        "class",
        "api",
        "refactor",
        "implementation",
        "debug",
    )
    if any(marker in lowered for marker in coding_markers):
        return "coding"
    reasoning_markers = ("prove", "reason", "analyze", "diagnose", "root cause", "math")
    if any(marker in lowered for marker in reasoning_markers):
        return "reasoning"
    creative_markers = ("write a story", "poem", "song", "brand", "creative", "script")
    if any(marker in lowered for marker in creative_markers):
        return "creative"
    fast_markers = ("quick", "short", "summarize", "simple", "fast")
    if any(marker in lowered for marker in fast_markers):
        return "fast"
    return "general"


def split_provider_model(entry: str) -> tuple[str, str]:
    """Split a fallback config entry into provider and model parts."""
    value = (entry or "").strip()
    if value.startswith("custom:"):
        value = value[len("custom:") :]
    if "/" not in value:
        return "", value
    provider, model = value.split("/", 1)
    return provider, model


def sort_fallback_entries_for_task(
    entries: Iterable[str],
    task_type: TaskType = "general",
) -> list[str]:
    """Sort fallback entries by static benchmark prior for a task type.

    Stable tie-breaker preserves existing order when two entries have equal prior.
    """
    indexed = list(enumerate(entries))

    def key(item: tuple[int, str]) -> tuple[float, int]:
        index, entry = item
        provider, model = split_provider_model(entry)
        return (benchmark_score(provider, model, task_type), -index)

    return [entry for _, entry in sorted(indexed, key=key, reverse=True)]
