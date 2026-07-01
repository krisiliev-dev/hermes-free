"""
Optional wrapper: boots a PipecatOrchestrator on /voice channel if Hermes
starts a voice session via DiscordAdapter, without changing adapter.py.
"""
from tools.pipecat_orchestrator import (
    HermesDiscordVoiceSTTHandle,
    HermesTTSHandle,
    maybe_start_pipecat_orchestrator,
    maybe_stop_pipecat_orchestrator,
    start_orchestrator,
    stop_orchestrator,
)

__all__ = [
    "maybe_start_pipecat_orchestrator",
    "maybe_stop_pipecat_orchestrator",
    "start_orchestrator",
    "stop_orchestrator",
    "HermesTTSHandle",
    "HermesDiscordVoiceSTTHandle",
]
