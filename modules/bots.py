# PubCast AI — bots.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
from __future__ import annotations

import asyncio
import threading
import logging
import os
import time
import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from pydantic import ValidationError

from .models import BotConfig, BotProvider, UserState
from .turn_requests import TurnRequests
from .persistence import read_json, write_json

if False:  # typing helpers without import cycle
    from modules.hub import Hub  # pragma: no cover

import contextvars
# Bots that keep working without any provider or API key: bot_id -> (module, label).
OFFLINE_RESPONDERS = {'pete': ('pete_character_runtime', 'Pete'),
                      'sir_purfluous': ('sir_purfluous_runtime', 'Sir Purfluous'),
                      'repeat': ('repete_runtime', 'RePete')}
# True when the most recent offline-capable reply in this task came from canned offline dialogue, not a model.
REPLY_WAS_OFFLINE: contextvars.ContextVar[bool] = contextvars.ContextVar('REPLY_WAS_OFFLINE', default=False)

logger = logging.getLogger(__name__)


@dataclass
class BotSession:
    config: BotConfig
    busy: bool = False
    last_reply_at: float = field(default=0.0)
    _pending_task: object = field(default=None, repr=False, compare=False)


class BotManager:
    """
    Coordinates AI co-hosts (ChatGPT, Gemini, etc.) so they can participate in rooms.
    Bots are virtual users that speak when their owner is present and the conversation calls for them.
    """

    def __init__(self, data_dir: Path, hub: "Hub", byok_mgr: Any = None):
        self.data_dir = data_dir
        self.hub = hub
        self._byok_mgr = byok_mgr   # injected after startup; may be None initially
        self._cricket_keeper = None
        self.config_dir = self.data_dir / "bots"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._configs: Dict[str, BotConfig] = {}
        self._sessions: Dict[str, BotSession] = {}
        self._lock = asyncio.Lock()
        self._config_lock = threading.Lock()
        self.turn_requests = TurnRequests(self.data_dir)
        self._room_turn_locks = {}
        self._background_bursts = {}
        self.reload()

    def set_byok_manager(self, byok_mgr: Any) -> None:
        """Wire in the BYOK manager after lifespan startup completes."""
        self._byok_mgr = byok_mgr

    def set_cricket_keeper(self, cricket_keeper: Any) -> None:
        """Optional Jeremy Cricket registry for per-bot memory."""
        self._cricket_keeper = cricket_keeper

    # ---------- lifecycle ----------
    def reload(self) -> None:
        with self._config_lock:
            self._reload_inner()

    def _reload_inner(self) -> None:
        self._configs.clear()
        self._sessions.clear()
        for path in self.config_dir.glob("*.json"):
            data = read_json(path)
            if not data:
                continue
            if not isinstance(data, dict):
                logger.error("Invalid bot config at %s: expected an object", path)
                continue
            if data.get("schema") == "pubcast.character-identity.v1":
                continue
            try:
                cfg = BotConfig(**data)
            except ValidationError as exc:
                logger.error("Invalid bot config at %s: %s", path, exc)
                continue
            # Enrich with canonical character profile if system_prompt is empty
            cfg = self._enrich_from_profile(cfg)
            self._configs[cfg.bot_id] = cfg
            self._sessions[cfg.bot_id] = BotSession(config=cfg)
            self._ensure_bot_profile(cfg)
        logger.info("Loaded %d bot configurations.", len(self._configs))

    @staticmethod
    def _enrich_from_profile(cfg: BotConfig) -> BotConfig:
        """Use the canonical character profile prompt when one exists.

        The profile's full system_prompt takes precedence over the (shorter)
        system_prompt stored in the bot's JSON file. If there is no profile for
        this bot, or the profile has no prompt, the bot's own system_prompt is
        kept exactly as it is. The JSON file on disk is never modified here.
        """
        try:
            from .character_profiles import EXTRA_CHARACTER_PROFILES
            profile = EXTRA_CHARACTER_PROFILES.get(cfg.bot_id)
            if profile and profile.system_prompt and profile.system_prompt.strip():
                if (cfg.system_prompt or "").strip() != profile.system_prompt.strip():
                    cfg = cfg.model_copy(update={"system_prompt": profile.system_prompt})
                    logger.info("Using canonical profile prompt for %s (%d chars)",
                                cfg.bot_id, len(profile.system_prompt))
        except ImportError:
            pass
        return cfg

    def list_configs(self) -> List[BotConfig]:
        return list(self._configs.values())

    def get_config(self, bot_id: str) -> Optional[BotConfig]:
        return self._configs.get(bot_id)

    def upsert_config(self, config: BotConfig) -> None:
        with self._config_lock:
            self._upsert_inner(config)

    def _upsert_inner(self, config: BotConfig) -> None:
        existing = self._configs.get(config.bot_id)
        if existing and existing.owner_id != config.owner_id:
            raise PermissionError("Bot ID already registered by another user.")

        path = self.config_dir / f"{config.bot_id}.json"
        write_json(path, config.model_dump())
        self._configs[config.bot_id] = config
        self._sessions[config.bot_id] = BotSession(config=config)
        self._ensure_bot_profile(config)
        logger.info("Registered bot %s (%s)", config.bot_id, config.provider)

    def delete_config(self, bot_id: str) -> None:
        with self._config_lock:
            self._delete_inner(bot_id)

    def _delete_inner(self, bot_id: str) -> None:
        path = self.config_dir / f"{bot_id}.json"
        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                logger.error("Unable to remove bot config %s: %s", path, exc)
        self._configs.pop(bot_id, None)
        self._sessions.pop(bot_id, None)
        logger.info("Removed bot %s", bot_id)

    def cricket_scope(self, cfg, room):
        identity = json.dumps(['room', cfg.owner_id, cfg.bot_id, room], separators=(',', ':'))
        return 'room_' + hashlib.sha256(identity.encode()).hexdigest()

    # ---------- runtime ----------
    async def on_chat_message(self, payload: Dict[str, Any]) -> None:
        """
        Consider responding to a new chat payload.
        """
        # Internal nudges target one bot and never trigger a room-wide response.
        if payload.get("nudge") or payload.get("user_id") == "__internal_nudge__":
            return
        if not self._configs:
            return
        room = payload["room"]
        if str(payload.get('user_id', '')).startswith('bot-'):
            self._background_bursts[room] = self._background_bursts.get(room, 0) + 1
            if self._background_bursts[room] >= 6:
                return
        else:
            self._background_bursts[room] = 0
        user_id = payload.get("user_id")
        text = payload.get("text", "")
        async with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            cfg = session.config
            bot_uid = self.bot_user_id(cfg.bot_id)
            if room not in cfg.rooms:
                continue
            if user_id == bot_uid:
                continue  # ignore our own echo
            if cfg.owner_id and not await self.hub.is_user_in_room(room, cfg.owner_id):
                continue  # owner not present
            if user_id and isinstance(user_id, str) and user_id.startswith("bot-") and not self._is_mention(cfg, text):
                continue  # avoid bot-to-bot chatter unless directly mentioned
            if not cfg.auto_reply and cfg.owner_id != user_id:
                # bot listens silently unless explicitly pinged
                if not self._is_mention(cfg, text):
                    continue
            if cfg.mention_only and not self._is_mention(cfg, text):
                continue
            if session.busy:
                continue
            await self._schedule_reply(session, payload)

    async def virtual_presence(self, room: str, present_user_ids: Set[str]) -> List[Dict[str, Any]]:
        """
        Provide bot profiles that should appear as co-present in a room (shadow presence).
        """
        result: List[Dict[str, Any]] = []
        if not self._configs:
            return result
        for cfg in self._configs.values():
            if not cfg.shadow_presence:
                continue
            if room not in cfg.rooms:
                continue
            if cfg.owner_id and cfg.owner_id not in present_user_ids:
                continue
            profile = self._ensure_bot_profile(cfg)
            if profile["user_id"] in present_user_ids:
                continue
            result.append(profile)
        return result

    async def nudge(self, room_id: str, hint: str, bot_id: str | None = None) -> bool:
        """Jeremy invites exactly one eligible partner; silence is an outcome."""
        async with self._lock:
            sessions = [s for s in self._sessions.values() if room_id in s.config.rooms
                        and not s.busy and (bot_id is None or s.config.bot_id == bot_id)
                        and s.config.settings.get('initiative_enabled', s.config.auto_reply)]
        if not sessions or self._background_bursts.get(room_id, 0) >= 6:
            return False
        # An owner must still be present; the conductor cannot wake absent users' AIs.
        sessions = [s for s in sessions if not s.config.owner_id or
                    await self.hub.is_user_in_room(room_id, s.config.owner_id)]
        if not sessions:
            return False
        target = min(sessions, key=lambda s: s.last_reply_at or 0)
        outcome = await self.request_turn(target.config.bot_id, room_id, hint, actor='system:jeremy', required=False)
        return outcome['state'] not in {'busy', 'unavailable'}

    async def request_turn(self, bot_id: str, room: str, hint: str, *, actor: str, required: bool):
        session = self._sessions.get(bot_id)
        if session is None or room not in session.config.rooms:
            raise ValueError('Partner is not configured for this room')
        cfg = session.config
        item = self.turn_requests.create(bot_id=bot_id, room=room, actor=actor, required=required)
        def update(state, **details):
            nonlocal item
            item = self.turn_requests.update(item, state, **details)
            witness = getattr(self.hub, 'blackbox_witness', None)
            if witness:
                witness.record_event('partner.turn_request', actor=actor, data=item)
            return item
        if cfg.owner_id and not await self.hub.is_user_in_room(room, cfg.owner_id):
            return update('unavailable', error='Partner owner is not present in the room')
        async with self._lock:
            if session.busy:
                return update('busy')
            session.busy = True
        room_lock = self._room_turn_locks.setdefault(room, asyncio.Lock())
        try:
            async with asyncio.timeout(120):
                async with room_lock:
                    if not required:
                        update('considering')
                        history = await self.hub.get_recent_history(room, limit=cfg.max_history)
                        if self._cricket_keeper is not None:
                            cricket = await self._cricket_keeper.get(self.cricket_scope(cfg, room))
                            history = await cricket.enrich_context(hint, history)
                        prompt = self._build_prompt(cfg, history, stage_hint=hint)
                        prompt += ('\nThis is a voluntary invitation to consider speaking. '
                                   'Decide for yourself. Return ONLY a JSON object with decision '
                                   'equal to accept, defer, or decline. Do not compose the speaking turn yet.')
                        REPLY_WAS_OFFLINE.set(False)
                        decision_text = await self._call_provider(cfg, prompt)
                        if REPLY_WAS_OFFLINE.get():
                            return update('failed', error='No live partner available to consider invitation')
                        try:
                            decision = json.loads(decision_text)['decision']
                        except (ValueError, KeyError, TypeError):
                            return update('failed', error='Partner invitation decision was not valid JSON')
                        if decision in {'defer', 'decline'}:
                            return update('deferred' if decision == 'defer' else 'declined')
                        if decision != 'accept':
                            return update('failed', error='Unknown invitation decision')
                        update('accepted')
                    update('speaking')
                    outcome = await self._generate_and_send(session, {
                        'room': room, 'user_id': '__internal_nudge__', 'user': actor,
                        'text': (("The host requires a speaking turn. Use your own words; you may disagree. " + hint) if required else hint), 'nudge': True, 'turn_request_id': item['request_id']})
                    if not outcome or not outcome.get('ok'):
                        return update('failed', error=(outcome or {}).get('error', 'No speaking turn was committed'))
                    return update('completed', offline=outcome.get('offline', False))
        except asyncio.CancelledError:
            update('interrupted', error='Turn was cancelled')
            raise
        except Exception as exc:
            logger.warning('Requested turn failed for %s: %s', bot_id, exc)
            return update('failed', error=str(exc))
        finally:
            session.busy = False

    async def shutdown(self):
        tasks = [s._pending_task for s in self._sessions.values() if s._pending_task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ---------- helpers ----------
    def bot_user_id(self, bot_id: str) -> str:
        return f"bot-{bot_id}"

    def _ensure_bot_profile(self, config: BotConfig) -> Dict[str, Any]:
        uid = self.bot_user_id(config.bot_id)
        user_file = self.data_dir / "users" / f"{uid}.json"
        existing = read_json(user_file)
        base = UserState(
            user_id=uid,
            display_name=config.name,
            avatar_color=self._default_color(config.provider),
            badge=config.provider.value.capitalize(),
        )
        merged = {**base.model_dump(), **existing}
        try:
            state = UserState(**merged)
        except ValidationError as exc:
            logger.warning("Bot profile for %s invalid (%s). Resetting.", uid, exc)
            state = base
        write_json(user_file, state.model_dump())
        if hasattr(self.hub, "invalidate_user_cache"):
            self.hub.invalidate_user_cache(uid)
        return state.model_dump()

    def _default_color(self, provider: BotProvider) -> str:
        if provider is BotProvider.OPENAI:
            return "#7b68ee"
        if provider is BotProvider.ANTHROPIC:
            return "#d4a843"   # Claude's brass/gold — matches the studio palette
        if provider is BotProvider.GEMINI:
            return "#3ddad7"
        return "#888888"

    def _is_mention(self, config: BotConfig, text: str) -> bool:
        lowered = (text or "").lower()
        name = config.name.lower()
        return f"@{name}" in lowered or lowered.strip().startswith(name)

    async def _schedule_reply(self, session: BotSession, payload: Dict[str, Any]) -> None:
        async with self._lock:
            if session.busy:
                return
            session.busy = True
        async def run():
            try:
                async with asyncio.timeout(120):
                    lock = self._room_turn_locks.setdefault(payload['room'], asyncio.Lock())
                    async with lock:
                        await self._generate_and_send(session, payload)
            finally:
                session.busy = False
        task = asyncio.create_task(run())
        # Store reference to prevent GC cancellation; task clears itself on completion.
        session._pending_task = task
        task.add_done_callback(lambda t: setattr(session, '_pending_task', None))

    async def _generate_and_send(self, session: BotSession, payload: Dict[str, Any]) -> Dict[str, Any] | None:
        cfg = session.config
        try:
            history = await self.hub.get_recent_history(payload["room"], limit=cfg.max_history)
            if self._cricket_keeper is not None:
                try:
                    cricket = await self._cricket_keeper.get(self.cricket_scope(cfg, payload["room"]))
                    incoming = (payload.get("text") or "").strip()
                    if incoming and payload.get("user_id") != self.bot_user_id(cfg.bot_id):
                        await cricket.remember(
                            content=f"{payload.get('user', payload.get('user_id', 'Someone'))}: {incoming}",
                            source="conversation",
                            importance=4,
                        )
                    history = await cricket.enrich_context(payload.get("text", ""), history)
                except Exception as memory_exc:
                    logger.warning("Jeremy Cricket memory failed for %s: %s", cfg.bot_id, memory_exc)
            prompt = self._build_prompt(cfg, history, stage_hint=payload.get("text") if payload.get("nudge") else None)
            if not prompt:
                return
            REPLY_WAS_OFFLINE.set(False)
            reply = await self._call_provider(cfg, prompt)
            if not reply:
                return {"ok": False, "error": "Provider returned no reply"}
            reply = reply.strip()
            if not reply:
                return
            await self.hub.post_chat_message(payload["room"], self.bot_user_id(cfg.bot_id), reply)
            session.last_reply_at = time.time()
            if self._cricket_keeper is not None:
                try:
                    cricket = await self._cricket_keeper.get(self.cricket_scope(cfg, payload["room"]))
                    await cricket.remember(content=reply, source="system", importance=5)
                except Exception as memory_exc:
                    logger.warning("Jeremy Cricket store failed for %s: %s", cfg.bot_id, memory_exc)
            return {"ok": True, "offline": REPLY_WAS_OFFLINE.get()}
        except Exception as exc:
            logger.exception("Bot %s failed to reply: %s", cfg.bot_id, exc)
            return {"ok": False, "error": str(exc)}
        finally:
            session.busy = False

    def _build_prompt(self, config: BotConfig, history: Sequence[Dict[str, Any]], stage_hint: Optional[str] = None) -> str:
        lines: List[str] = []
        if config.system_prompt:
            lines.append(f"System instruction: {config.system_prompt.strip()}")
        if stage_hint:
            lines.append(f"Stage direction (private): {stage_hint.strip()}")
        for entry in history:
            if entry.get("role") == "system":
                text = entry.get("text", "")
                if text:
                    lines.append(text)
                continue
            user = entry.get("user") or entry.get("sender_id") or entry.get("participant_id") or "User"
            text = entry.get("text", "")
            lines.append(f"{user}: {text}")
        lines.append(f"{config.name}:")
        return "\n".join(lines)

    async def _call_provider(self, config: BotConfig, prompt: str) -> str:
        # The speaking model is primary. The local canonical responder is an
        # explicitly limited contingency if credentials or provider are unavailable.
        if config.bot_id in OFFLINE_RESPONDERS:
            import re
            from importlib import import_module
            _mod, _label = OFFLINE_RESPONDERS[config.bot_id]
            respond = import_module(f".{_mod}", __package__).respond

            def offline_reply() -> str:
                REPLY_WAS_OFFLINE.set(True)
                lines = prompt.rstrip().splitlines()
                latest = "status"
                for line in reversed(lines[:-1]):
                    if re.match(r"^(?:[^:\n]{1,128}):\s+", line) and not line.startswith("System instruction:"):
                        latest = line.split(":", 1)[1].strip()
                        break
                hist = []
                for line in lines[:-1]:
                    if ": " in line and not line.startswith("System instruction:"):
                        who, _, said = line.partition(": ")
                        hist.append({"speaker": who, "text": said})
                return respond(latest, hist)

            if config.settings.get("offline_character", False):
                return offline_reply()
            try:
                if config.provider is BotProvider.OPENAI:
                    answer = await self._call_openai(config, prompt)
                elif config.provider is BotProvider.ANTHROPIC:
                    answer = await self._call_anthropic(config, prompt)
                elif config.provider is BotProvider.GEMINI:
                    answer = await self._call_gemini(config, prompt)
                elif config.provider is BotProvider.OLLAMA:
                    answer = await self._call_ollama(config, prompt)
                else:
                    raise RuntimeError(f"Unsupported provider {config.provider}")
                if answer and answer.strip():
                    return answer
                raise RuntimeError("Speaking provider returned an empty response")
            except Exception as exc:
                if not config.settings.get("offline_fallback", True):
                    raise
                logger.warning("%s's speaking provider unavailable; using limited offline dialogue: %s", _label, exc)
                return offline_reply()
        if config.provider is BotProvider.OPENAI:
            return await self._call_openai(config, prompt)
        if config.provider is BotProvider.ANTHROPIC:
            return await self._call_anthropic(config, prompt)
        if config.provider is BotProvider.GEMINI:
            return await self._call_gemini(config, prompt)
        if config.provider is BotProvider.OLLAMA:
            return await self._call_ollama(config, prompt)
        raise RuntimeError(f"Unsupported provider {config.provider}")

    async def _call_anthropic(self, config: BotConfig, prompt: str) -> str:
        api_key = self._get_api_key(config)
        try:
            import anthropic as _anthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "anthropic package is not installed. Run `pip install anthropic`."
            ) from exc
        client = _anthropic.AsyncAnthropic(api_key=api_key)
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict = {
            "model":      config.model,
            "max_tokens": config.max_history * 50,   # rough budget from config
            "messages":   messages,
        }
        if config.system_prompt.strip():
            kwargs["system"] = config.system_prompt
        response = await client.messages.create(**kwargs)
        return response.content[0].text if response.content else ""

    async def _call_openai(self, config: BotConfig, prompt: str) -> str:
        api_key = self._get_api_key(config)
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Run `pip install openai`.") from exc
        client = AsyncOpenAI(api_key=api_key)
        messages = [{"role": "user", "content": prompt}]
        if config.system_prompt.strip():
            messages = [{"role": "system", "content": config.system_prompt}] + messages
        response = await client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
        )
        return response.choices[0].message.content or ""

    async def _call_gemini(self, config: BotConfig, prompt: str) -> str:
        api_key = self._get_api_key(config)
        try:
            from google import genai as google_genai  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "google-genai package is not installed. Run `pip install google-genai`."
            ) from exc
        client = google_genai.Client(api_key=api_key)
        full_prompt = prompt
        if config.system_prompt.strip():
            full_prompt = f"{config.system_prompt}\n\n{prompt}"

        def _generate() -> str:
            response = client.models.generate_content(
                model=config.model,
                contents=full_prompt,
                config={"temperature": config.temperature},
            )
            return response.text or ""

        return await asyncio.to_thread(_generate)

    async def _call_ollama(self, config: BotConfig, prompt: str) -> str:
        try:
            from .llm_orchestrator import ContextPacket, VALID_ROLES, get_orchestrator

            requested_role = (os.getenv("PUBCAST_BOT_LLM_ROLE", "studio") or "studio").strip().lower()
            if requested_role not in VALID_ROLES:
                requested_role = "studio"

            ctx = ContextPacket(
                character_name=config.name,
                system_prompt=config.system_prompt or "",
            )
            result = await get_orchestrator().generate(
                prompt,
                role=requested_role,
                context=ctx,
                temperature=config.temperature,
                max_tokens=160,
                studio_model=(config.model or "").strip() or None,
            )
            if result.text:
                return result.text
            logger.warning(
                "Orchestrator path failed for bot %s (role=%s). Falling back to direct Ollama.",
                config.bot_id,
                requested_role,
            )
        except Exception as exc:
            logger.debug("Orchestrator path unavailable for bot %s: %s", config.bot_id, exc)

        import httpx
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model = config.model or os.getenv("OLLAMA_MODEL", "ministral-pubcast:3b")
        timeout = float(os.getenv("OLLAMA_TIMEOUT", "180"))
        keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "1h")
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{host}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": keep_alive,
                        "options": {
                            "temperature": config.temperature,
                            "num_ctx": 2048,
                            "num_predict": 160,
                        },
                    },
                )
                response.raise_for_status()
                return response.json().get("response", "")
        except Exception as exc:
            logger.warning("Ollama call failed for %s: %s", config.bot_id, exc)
            return ""

    def _get_api_key(self, config: BotConfig) -> str:
        """
        Key resolution order:
          1. BYOK store — user-registered key for this provider (most specific)
          2. Environment variable (host-level key, works for all users)
          3. Raise RuntimeError with a clear message pointing to BYOK

        The BYOK lookup uses a synthetic user_id "host" for host-level keys so
        operators can register a default key without needing a real user session.
        """
        # 1. BYOK store lookup
        if self._byok_mgr is not None:
            provider = config.provider.value if hasattr(config.provider, 'value') else str(config.provider)
            try:
                import asyncio as _aio
                # get_adapter resolves the best key for this provider
                session_key = f"host:{provider}"
                stored = self._byok_mgr._store.get_model("host", provider)
                if stored:
                    key = self._byok_mgr._store.get_secret("host", provider, "api_key") or ""
                    if key:
                        logger.debug("Bot %s using BYOK key for provider=%s", config.bot_id, provider)
                        return key
                # Also check by model_id matching provider name
                for m in self._byok_mgr._store.list_models("host"):
                    if m.provider == provider:
                        key = self._byok_mgr._store.get_secret("host", m.model_id, "api_key") or ""
                        if key:
                            logger.debug("Bot %s using BYOK key model=%s", config.bot_id, m.model_id)
                            return key
            except Exception as exc:
                logger.debug("BYOK lookup failed for bot %s: %s", config.bot_id, exc)

        # 2. Environment variable
        key = os.getenv(config.api_key_env, "").strip()
        if key:
            return key

        # 3. Nothing found
        raise RuntimeError(
            f"No API key found for {config.name} (provider={config.provider}). "
            f"Either set env var '{config.api_key_env}' or register a key at /byok."
        )
