"""
Pipecat-family voice-mode orchestrator (console or Discord).

This module owns the lightweight shim symbols imported by
``plugins/platforms/discord/discord_voice_mode_wrapper`` and exposes
lightweight wrappers for TTS + STT so the wrapper is self-contained.
If ``pipecat``/``pipecat-ai`` is unavailable it degrades gracefully.
"""

from __future__ import annotations

import asyncio
import logging
import typing
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

_active: dict[int, bool] = {}


@dataclass
class _GuildState:
    reply_fn: Callable[[str], Awaitable[str]]
    stt: Optional[typing.Any] = None
    tts: Optional[typing.Any] = None
    pending_replies: list[str] = field(default_factory=list)
    background_tasks: list[Awaitable] = field(default_factory=list)


class _BaseHandle:
    def __init__(self, adapter, guild_id: int):
        self.adapter = adapter
        self.guild_id = guild_id


class HermesTTSHandle(_BaseHandle):
    async def speak(self, text: str, *, wait: bool = False) -> None:
        state = self.adapter._voice_orchestrator_state  # type: ignore[attr-defined]
        guild_state = state.setdefault(self.guild_id, _GuildState(reply_fn=state["_reply_fn"]))  # type: ignore[index]
        try:
            chat_ids = getattr(self.adapter, "_voice_text_channels", {})
            text_ch_id = chat_ids.get(self.guild_id)
            if not text_ch_id:
                return
            from tools.text_to_speech import text_to_speech
            client = text_to_speech(text)
            path = getattr(client, "path", None)
            if not path:
                return
            await self.adapter.play_tts(str(text_ch_id), path)
            guild_state.pending_replies.append(text)
            if not wait:
                asyncio.create_task(
                    self.adapter._voice_input_callback(
                        guild_id=self.guild_id,
                        user_id=getattr(self.adapter, "_voice_bot_user_id", 0),
                        transcript=text,
                    )
                )
        except Exception as exc:
            logger.debug("HermesTTSHandle.speak skipped: %s", exc)


class HermesDiscordVoiceSTTHandle(_BaseHandle):
    async def start(self):
        receiver = getattr(self.adapter, "_voice_receivers", {}).get(self.guild_id)
        if receiver is None:
            return
        try:
            receiver.resume()
        except Exception:
            pass


async def maybe_start_pipecat_orchestrator(
    adapter,
    guild_id: int,
    *,
    reply_fn,
) -> None:
    try:
        reply_fn_name = getattr(reply_fn, "__name__", repr(reply_fn))
    except Exception:
        reply_fn_name = repr(reply_fn)
    active_before = _active.get(guild_id, False)
    _active[guild_id] = True
    state = getattr(adapter, "_voice_orchestrator_state", None)
    if state is None:
        state = {}
        try:
            adapter._voice_orchestrator_state = state  # type: ignore[attr-defined]
        except Exception:
            pass
    state[guild_id] = _GuildState(reply_fn=reply_fn)
    state["_reply_fn"] = reply_fn  # type: ignore[index]
    if not active_before:
        logger.info("[voice] streaming mode enabled for guild=%s", guild_id)
        logger.debug("[voice] reply_fn=%s", reply_fn_name)


async def maybe_stop_pipecat_orchestrator(guild_id: int) -> None:
    active_before = _active.get(guild_id, False)
    _active.pop(guild_id, None)
    if active_before:
        logger.info("[voice] streaming mode disabled for guild=%s", guild_id)


async def start_orchestrator(
    adapter,
    guild_id: int,
    *,
    reply_fn: Callable[[str], Awaitable[str]],
    stt=None,
    tts=None,
    on_state_change: Optional[Callable[[str], None]] = None,
) -> None:
    await maybe_start_pipecat_orchestrator(adapter, guild_id, reply_fn=reply_fn)


async def stop_orchestrator(guild_id: int) -> None:
    await maybe_stop_pipecat_orchestrator(guild_id)
