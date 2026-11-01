"""Serialize a spine's owner/session turns without retaining idle lock entries.

This is deliberately process-local, matching the single-process local launcher.
Multi-worker deployments require a shared lock/queue and are not supported here.
"""
import asyncio
from functools import wraps
from weakref import WeakValueDictionary


def serialized_turn(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        if not hasattr(self, '_live_turn_locks'):
            self._live_turn_locks = WeakValueDictionary()
        key = (kwargs.get('user_id', 'anon'), kwargs.get('session_id', 'default'))
        lock = self._live_turn_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._live_turn_locks[key] = lock
        async with lock:
            return await method(self, *args, **kwargs)
    return wrapped
