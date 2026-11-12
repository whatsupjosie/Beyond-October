"""Runtime witness bridge for PubCast BlackBox.

This module keeps the impartial flight recorder outside player-facing UI while
letting camera, recording, studio, and AI systems report compact known events.
It records facts only: what system acted, what changed, and the small payload
PubCast already knows at the boundary.
"""
from __future__ import annotations

import logging
import time
import uuid
import threading
import re
import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .blackbox_media import BlackBoxMedia

from blackbox_recorder import AppendOnlyBlackBoxRecorder, record_pubcast_event

logger = logging.getLogger("pubcast.blackbox_runtime")


@dataclass(frozen=True)
class BlackBoxStatus:
    enabled: bool
    session_id: str
    path: str
    next_seq: int
    previous_hash: str
    compute_budget_percent: float


class BlackBoxRuntimeWitness:
    """Small append-only witness used by runtime systems.

    The witness is intentionally boring and defensive: if BlackBox recording
    fails, production code keeps running and the failure is logged normally.
    """

    def __init__(self, data_dir: Path | str, session_id: Optional[str] = None, enabled: bool = True):
        self._lock = threading.RLock()
        self._closed = False
        self._error = None
        self._failed_events = 0
        self._pending_failures = 0
        self._last_failure = None
        self._chat_outbox = None
        self._chat_replay = {'state':'inactive','pending':None,'replayed':0}
        self._chat_task = None
        self._chat_stop = None
        self._archive_policy = None
        self.data_dir = Path(data_dir)
        self.session_id = session_id or f"pubcast_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', self.session_id):
            raise ValueError('Blackbox session ID must be a single safe filename component')
        self.enabled = bool(enabled)
        self.path = self.data_dir / "blackbox" / f"{self.session_id}.bbx"
        self._recorder = AppendOnlyBlackBoxRecorder(self.path, self.session_id)
        self.media = BlackBoxMedia(self.data_dir)
        if self.enabled:
            self.record_event(
                "runtime.blackbox_ready",
                source="blackbox",
                actor="system:blackbox",
                data={"session_id": self.session_id, "mode": "external_boundary"},
            )

    @property
    def recorder(self) -> AppendOnlyBlackBoxRecorder:
        return self._recorder

    def status(self) -> BlackBoxStatus:
        return BlackBoxStatus(
            enabled=self.enabled,
            session_id=self.session_id,
            path=str(self.path),
            next_seq=self._recorder.next_seq,
            previous_hash=self._recorder.previous_hash,
            compute_budget_percent=self._recorder.compute_budget_percent,
        )

    def record_event(
        self,
        event_type: str,
        *,
        source: str = "system",
        actor: str = "SYS",
        data: Optional[Mapping[str, Any]] = None,
    ) -> Optional[str]:
        with self._lock:
            if not self.enabled or self._closed:
                return None
            try:
                event = {
                    "event_type": event_type,
                    "source": source,
                    "actor": actor,
                    "data": dict(data) if data is not None else {},
                }
                if self._pending_failures:
                    # An acknowledgement of lost coverage, not a replay of the
                    # missing events. Commit before the next successful event.
                    record_pubcast_event(self._recorder, {
                        'event_type':'runtime.coverage_gap', 'source':'blackbox',
                        'actor':'SYS', 'data':{'failed_events':self._pending_failures,
                            'last_failed_event':self._last_failure['event_type'],
                            'last_failure_at':self._last_failure['at']}})
                    self._pending_failures = 0
                result = record_pubcast_event(self._recorder, event)
                self._error = None
                return result
            except Exception as exc:  # pragma: no cover - runtime safety belt
                self._error = str(exc)
                self._failed_events += 1
                self._pending_failures += 1
                self._last_failure = {'event_type':str(event_type),
                                      'error_type':type(exc).__name__, 'at':time.time()}
                logger.warning("BlackBox witness failed for %s: %s", event_type, exc)
                return None

    def health(self):
        # A status poll does a real durable write. Configuration alone cannot
        # turn the connection green, and this never turns the capture green.
        with self._lock:
            state = 'inactive'
            if self.enabled and not self._closed:
                state = 'running' if self.record_event('runtime.heartbeat', source='blackbox') else 'crashed'
            media = self.media.status()
            return {'connection': state, 'recording': media['state'],
                    'coverage':'degraded' if (self._failed_events or
                        self._chat_replay.get('state')=='blocked' or self._chat_replay.get('pending') or
                        self._chat_replay.get('unidentified')) else 'no_known_gaps',
                    'coverage_scope':'current_process',
                    'failed_events':self._failed_events, 'last_failure':self._last_failure,
                    'chat_replay':dict(self._chat_replay),
                    'session_id': self.session_id, 'captures': media['captures'],
                    'recovery_issues': media.get('recovery_issues', [])}

    def _outbox(self):
        if self._chat_outbox is None:
            from .blackbox_chat_replay import ChatWitnessOutbox
            self._chat_outbox = ChatWitnessOutbox(self)
        return self._chat_outbox

    def archive_policy_store(self):
        with self._lock:
            if self._archive_policy is None:
                from .blackbox_retention_policy import ArchivePolicyStore
                self._archive_policy=ArchivePolicyStore(self.data_dir)
            return self._archive_policy

    def archive_policy(self):
        with self._lock:
            return self.archive_policy_store().capacity()

    def update_archive_policy(self,body,actor):
        with self._lock:
            store=self.archive_policy_store()
            result=store.update(body,actor)
            warnings=[]
            try:pending=store.deliver_audits(self)
            except (OSError,sqlite3.Error):
                pending=None
                warnings.append('Settings saved; Blackbox audit delivery awaits retry')
            try:capacity=store.capacity()
            except (OSError,sqlite3.Error):
                capacity={'disk_free_bytes':None,'disk_total_bytes':None,'preallocated':False}
                warnings.append('Settings saved; disk capacity could not be refreshed')
            return {**result,'pending_audit_records':pending,'warnings':warnings,**{
                key:value for key,value in capacity.items() if key not in result}}

    def record_chat(self, message):
        """Queue an already committed canonical message; acknowledge once only."""
        with self._lock:
            if not self.enabled or self._closed:return False
            try:
                outbox=self._outbox()
                identity=outbox.enqueue(message)
                acknowledged=outbox.deliver(identity,replay=False)
                pending=outbox.pending()
                self._chat_replay.update(state='blocked' if self._chat_replay.get('archive_errors') or
                    self._chat_replay.get('unidentified') else ('backlog' if pending else 'running'),pending=pending)
                self._chat_replay.pop('error_type',None)
                return acknowledged
            except Exception as error:
                self._chat_replay.update(state='blocked',error_type=type(error).__name__)
                if self._chat_outbox is not None:
                    try:self._chat_replay['pending']=self._chat_outbox.pending()
                    except Exception:self._chat_replay['pending']=None
                logger.warning('Chat witness queued/recoverable from archive; delivery failed: %s',type(error).__name__)
                return False

    def recover_chat(self):
        """Reconcile archive/outbox receipts, without rebroadcasting or AI calls."""
        with self._lock:
            if not self.enabled or self._closed:
                return {**self._chat_replay,'state':'inactive'}
            try:
                if self._recorder._write_failed:
                    verified=self._recorder.verify()
                    if not verified.ok:raise OSError('Writer recovery requires an intact ledger')
                    self._recorder=AppendOnlyBlackBoxRecorder(self.path,self.session_id)
                    if not self.record_event('runtime.blackbox_recovered',source='blackbox'):
                        raise OSError('Writer recovery receipt failed')
                self._chat_replay=self._outbox().recover()
                # Settings history is durable independently of the BBX receipt;
                # replay only audit observations, never the setting mutation.
                self.archive_policy_store().deliver_audits(self)
            except Exception as error:
                self._chat_replay.update(state='blocked',error_type=type(error).__name__)
                if self._chat_outbox is not None:
                    try:self._chat_replay['pending']=self._chat_outbox.pending()
                    except Exception:self._chat_replay['pending']=None
                logger.warning('Automatic chat replay blocked: %s',type(error).__name__)
            return dict(self._chat_replay)

    async def start_chat_replay(self, interval=2.0):
        if self._chat_task is not None or not self.enabled:return
        if interval <= 0:raise ValueError('Chat replay interval must be positive')
        await asyncio.to_thread(self.recover_chat)
        self._chat_stop=asyncio.Event()
        async def run():
            while not self._chat_stop.is_set():
                try:
                    await asyncio.wait_for(self._chat_stop.wait(),timeout=interval)
                except asyncio.TimeoutError:
                    await asyncio.to_thread(self.recover_chat)
        self._chat_task=asyncio.create_task(run(),name='blackbox-chat-replay')

    async def stop_chat_replay(self):
        if self._chat_task is not None:
            self._chat_stop.set()
            await self._chat_task  # Finish any worker-thread delivery before witness.close().
            self._chat_task=None
            self._chat_stop=None

    def internal_audit_logger(self, legacy_logger):
        """Mirror an existing internal audit envelope without changing its file.

        A caller may approve an action only when both writes succeeded. These
        are independent files, not a distributed transaction; partial writes
        remain as evidence and are never rolled back or silently retried.
        """
        def log(data_dir, event):
            if Path(data_dir).resolve() != self.data_dir.resolve():
                raise ValueError('Internal audit belongs to a different runtime')
            legacy_logger(data_dir, event)
            if not self.record_event('internal.audit',
                    source=str(event.get('source') or 'pub_manager'),
                    actor=str(event.get('user_id') or event.get('acting_identity') or 'SYS'),
                    data={'event':dict(event)}):
                raise OSError('Internal audit Blackbox receipt failed')
        return log

    def close(self):
        with self._lock:
            if self._closed:
                return
            try:
                self.media.close()
                if self.enabled and not self.record_event('runtime.blackbox_stopped', source='blackbox'):
                    raise OSError('Unable to commit Blackbox shutdown marker')
            finally:
                self._closed = True

    def reopen(self):
        with self._lock:
            if not self._closed:
                return
            if not self.enabled:
                self._closed = False
                return
            verified = self._recorder.verify()
            if not verified.ok:
                raise OSError('Blackbox reopen refused: ' + '; '.join(verified.errors[:3]))
            # A failed fsync may have left a complete line on disk. Reload
            # sequence/hash from verified bytes rather than reusing stale state.
            recorder = AppendOnlyBlackBoxRecorder(self.path, self.session_id)
            self._recorder = recorder
            self._closed = False
            if self.enabled and not self.record_event('runtime.blackbox_restarted', source='blackbox'):
                self._closed = True
                raise OSError('Blackbox restart receipt could not be committed')

    def access(self, actor: str, access: str, scope: str = "status", reason: str = "operator_check") -> Optional[str]:
        with self._lock:
            if not self.enabled or self._closed:
                return None
            try:
                return self._recorder.access(actor=actor, access=access, scope=scope, reason=reason)
            except Exception as exc:  # pragma: no cover
                logger.warning("BlackBox access record failed: %s", exc)
                return None

    def crash_position(self, signal: str, known: Optional[Mapping[str, Any]] = None) -> bool:
        with self._lock:
            if not self.enabled or self._closed:
                return False
            try:
                self._recorder.crash_position(signal, known or {})
                return True
            except Exception as exc:  # pragma: no cover
                logger.warning("BlackBox crash-position record failed: %s", exc)
                return False

    def verify(self):
        return self._recorder.verify()


def create_blackbox_witness(data_dir: Path | str, *, session_id: Optional[str] = None, enabled: bool = True) -> BlackBoxRuntimeWitness:
    return BlackBoxRuntimeWitness(data_dir, session_id=session_id, enabled=enabled)


__all__ = ["BlackBoxRuntimeWitness", "BlackBoxStatus", "create_blackbox_witness"]
