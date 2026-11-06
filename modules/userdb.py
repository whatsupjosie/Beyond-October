# PubCast AI — userdb.py
# Copyright © 2024–2026 Josie Curtsey Cobbley (Joshua Cobbley)
# Rearview Foresight LLC — All Rights Reserved
# Feic Mo Chroí — See My Heart
"""
modules/userdb.py — Async SQLite-backed user database.

Exports:
    init_db()
    get_user(username: str) -> dict | None
    create_user(username: str, password: str, role: str) -> bool
    create_owner_if_not_exists()
    record_mod_action(room: str, operator: str, action: str, detail: str)
    get_mod_actions(room: str, limit: int) -> list[dict]
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .auth import get_password_hash

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB location — resolved once at import time, overridable via env
# ---------------------------------------------------------------------------
_DB_PATH: Path = Path(os.environ.get("PUBCAST_DATA_DIR", "data")) / "users.db"

# SQLite is synchronous; we run it in a thread executor to avoid blocking
# the asyncio event loop.
_executor: Optional[asyncio.AbstractEventLoop] = None
_SETUP_LOCK = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _sync_init_db() -> None:
    """Create tables if they don't exist. Runs synchronously."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_connection()
    try:
        c = conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                username        TEXT PRIMARY KEY,
                hashed_password TEXT NOT NULL,
                role            TEXT NOT NULL DEFAULT 'guest',
                created_at      REAL NOT NULL DEFAULT (strftime('%s','now'))
            );

            CREATE TABLE IF NOT EXISTS mod_actions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                room        TEXT NOT NULL,
                operator    TEXT NOT NULL,
                action      TEXT NOT NULL,
                detail      TEXT NOT NULL DEFAULT '',
                ts          REAL NOT NULL DEFAULT (strftime('%s','now'))
            );

            CREATE INDEX IF NOT EXISTS idx_mod_actions_room ON mod_actions(room, ts DESC);

            -- The PubCast profile. user_id is permanent: made once, never reused or changed, so everything a person
            -- owns (notes, records) stays theirs whatever their display name or username becomes.
            CREATE TABLE IF NOT EXISTS profiles (
                user_id         TEXT PRIMARY KEY,
                username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name    TEXT NOT NULL DEFAULT '',
                email           TEXT NOT NULL DEFAULT '',
                created_at      REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS visiting_profiles (
                user_id TEXT PRIMARY KEY,
                card_json TEXT NOT NULL,
                card_at REAL NOT NULL
            );
        """)
        conn.execute('BEGIN IMMEDIATE')
        columns = {row[1] for row in conn.execute('PRAGMA table_info(profiles)')}
        for column, declaration in {
            'details_json':"TEXT NOT NULL DEFAULT '{}'",
            'profile_revision':'INTEGER NOT NULL DEFAULT 0',
            'photo_data':'BLOB', 'photo_sha256':"TEXT NOT NULL DEFAULT ''",
        }.items():
            if column not in columns:
                conn.execute(f'ALTER TABLE profiles ADD COLUMN {column} {declaration}')
        _sync_backfill_profiles(conn)
        conn.commit()
        logger.info("userdb: tables ready at %s", _DB_PATH)
    finally:
        conn.close()




# ---------------------------------------------------------------------------
# PubCast profiles
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
DISPLAY_NAME_MAX = 80
EMAIL_MAX = 254


def new_user_id() -> str:
    """A permanent, random user ID: 'u_' and 20 hex digits (80 bits)."""
    return "u_" + secrets.token_hex(10)


def clean_email(value: Optional[str]) -> str:
    """'' for no email; otherwise a trimmed address, or ValueError if it is not one."""
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) > EMAIL_MAX or not EMAIL_RE.fullmatch(value):
        raise ValueError("That email address does not look right")
    return value


def clean_display_name(value: Optional[str], fallback: str) -> str:
    value = " ".join((value or "").split())
    if len(value) > DISPLAY_NAME_MAX:
        raise ValueError(f"Display name is longer than {DISPLAY_NAME_MAX} characters")
    return value or fallback


def _insert_profile(conn: sqlite3.Connection, username: str, display_name: str = "", email: str = "") -> str:
    user_id = new_user_id()
    conn.execute(
        "INSERT INTO profiles (user_id, username, display_name, email, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, display_name or username, email, time.time()),
    )
    return user_id


def _sync_backfill_profiles(conn: sqlite3.Connection) -> int:
    """Every account gets a profile. Accounts made before profiles existed get one now, once."""
    rows = conn.execute(
        "SELECT u.username FROM users u LEFT JOIN profiles p ON p.username = u.username COLLATE NOCASE "
        "WHERE p.user_id IS NULL"
    ).fetchall()
    for row in rows:
        _insert_profile(conn, row["username"])
    if rows:
        logger.info("userdb: made profiles for %d existing account(s)", len(rows))
    return len(rows)


_PROFILE_COLS = "p.user_id, p.username, p.display_name, p.email, p.created_at, u.role, p.details_json, p.profile_revision, p.photo_sha256"


def _profile_dict(row) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    from .human_profiles import details
    value = dict(row)
    value['details'] = details(json.loads(value.pop('details_json', '{}')))
    return value


def _visiting_profile(conn, user_id):
    row = conn.execute('SELECT * FROM visiting_profiles WHERE user_id=?', (user_id,)).fetchone()
    if row is None:
        return None
    card = json.loads(row['card_json'])
    return dict(user_id=card['user_id'], username=card['username'], display_name=card['display_name'],
                email='', role='guest', created_at=row['card_at'], details=card['details'],
                profile_revision=0, photo_sha256='', visiting=True)


def _sync_save_visiting_profile(card, card_at):
    """Cache only an admitted signed public card; no local user/password is made."""
    conn = _get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT 1 FROM profiles WHERE user_id=?', (card['user_id'],)).fetchone():
            raise ValueError('A visitor cannot replace a local profile')
        conn.execute('''INSERT INTO visiting_profiles VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE
                        SET card_json=excluded.card_json, card_at=excluded.card_at
                        WHERE excluded.card_at>visiting_profiles.card_at''',
                     (card['user_id'], json.dumps(card), card_at))
        conn.commit()
    finally:
        conn.close()


def _sync_get_profile_by_username(username: str) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        row = conn.execute(
            f"SELECT {_PROFILE_COLS} FROM profiles p JOIN users u ON u.username = p.username COLLATE NOCASE "
            "WHERE p.username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if row is None and conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            _sync_backfill_profiles(conn)                 # an account made by an older path: give it its profile now
            conn.commit()
            row = conn.execute(
                f"SELECT {_PROFILE_COLS} FROM profiles p JOIN users u ON u.username = p.username COLLATE NOCASE "
                "WHERE p.username = ? COLLATE NOCASE",
                (username,),
            ).fetchone()
        return _profile_dict(row) if row else _visiting_profile(conn, username)
    finally:
        conn.close()


def _sync_get_profile(user_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        row = conn.execute(
            f"SELECT {_PROFILE_COLS} FROM profiles p JOIN users u ON u.username = p.username COLLATE NOCASE "
            "WHERE p.user_id = ?",
            (user_id,),
        ).fetchone()
        return _profile_dict(row) if row else _visiting_profile(conn, user_id)
    finally:
        conn.close()


def _sync_list_profiles() -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        if _sync_backfill_profiles(conn):            # any account made by an older path shows up in the production too
            conn.commit()
        rows = conn.execute(
            f"SELECT {_PROFILE_COLS} FROM profiles p JOIN users u ON u.username = p.username COLLATE NOCASE "
            "ORDER BY p.created_at ASC"
        ).fetchall()
        visitors = conn.execute('SELECT user_id FROM visiting_profiles ORDER BY card_at').fetchall()
        return [_profile_dict(r) for r in rows] + [_visiting_profile(conn, r['user_id']) for r in visitors]
    finally:
        conn.close()


def _sync_update_profile(user_id: str, display_name: Optional[str], email: Optional[str], profile_details=None, expected_revision=None) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT username, profile_revision FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        if expected_revision is not None and expected_revision != row['profile_revision']:
            raise ValueError('Profile changed in another window; reload it before saving')
        if profile_details is not None:
            from .human_profiles import details
            conn.execute('UPDATE profiles SET details_json=? WHERE user_id=?',
                         (json.dumps(details(profile_details)),user_id))
        if display_name is not None:
            conn.execute("UPDATE profiles SET display_name = ? WHERE user_id = ?",
                         (clean_display_name(display_name, row["username"]), user_id))
        if email is not None:
            conn.execute("UPDATE profiles SET email = ? WHERE user_id = ?", (clean_email(email), user_id))
        conn.execute('UPDATE profiles SET profile_revision=profile_revision+1 WHERE user_id=?',(user_id,))
        conn.commit()
    finally:
        conn.close()
    return _sync_get_profile(user_id)


def _sync_create_member(username: str, password: str, role: str, display_name: str, email: str) -> Optional[str]:
    """Make a crew account and its profile together. Returns the new user_id, or None if the username is taken."""
    if role not in {"guest", "mod"}:
        raise ValueError("A crew account is either guest or mod")
    email = clean_email(email)
    display_name = clean_display_name(display_name, username)
    hashed = get_password_hash(password)
    conn = _get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        taken = conn.execute("SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone() or \
            conn.execute("SELECT 1 FROM profiles WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
        if taken:
            conn.rollback()
            return None
        conn.execute("INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)", (username, hashed, role))
        user_id = _insert_profile(conn, username, display_name, email)
        conn.commit()
        logger.info("userdb: crew account '%s' (%s) created", username, role)
        return user_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sync_count_users() -> int:
    conn = _get_connection()
    try:
        return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        conn.close()


def _sync_create_owner_via_setup(username: str, password: str, email: str = "", display_name: str = "", discoverable: bool = False) -> bool:
    """Atomically create the first owner account.

    Returns False when setup has already been completed. BEGIN IMMEDIATE plus
    a process lock closes the race between two concurrent first-run requests.
    """
    hashed = get_password_hash(password)
    with _SETUP_LOCK:
        conn = _get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            count = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            if count != 0:
                conn.rollback()
                return False
            conn.execute(
                "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, 'owner')",
                (username, hashed),
            )
            uid=_insert_profile(conn, username, clean_display_name(display_name, username), clean_email(email))
            from .human_profiles import details
            conn.execute('UPDATE profiles SET details_json=? WHERE user_id=?',
                         (json.dumps(details({'discoverable':discoverable})),uid))
            conn.commit()
            logger.info("userdb: first-run owner account '%s' created", username)
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _sync_update_password_hash(username: str, hashed_password: str) -> bool:
    conn = _get_connection()
    try:
        cur = conn.execute(
            "UPDATE users SET hashed_password = ? WHERE username = ?",
            (hashed_password, username),
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def _sync_get_user(username: str) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT username, hashed_password, role, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _sync_create_user(username: str, password: str, role: str) -> bool:
    """Insert user. Returns False if username already exists."""
    hashed = get_password_hash(password)
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
            (username, hashed, role),
        )
        conn.commit()
        logger.info("userdb: created user '%s' with role '%s'", username, role)
        return True
    except sqlite3.IntegrityError:
        logger.debug("userdb: user '%s' already exists", username)
        return False
    finally:
        conn.close()


def _sync_create_owner_if_not_exists() -> None:
    """
    Create the default owner account if no users exist yet.
    Credentials are pulled from environment variables so they are never
    hard-coded.  Falls back to insecure defaults with a loud warning.
    """
    owner_name = os.environ.get("PUBCAST_OWNER_USERNAME", "owner")
    owner_pass = os.environ.get("PUBCAST_OWNER_PASSWORD", "")

    if not owner_pass:
        logger.warning(
            "PUBCAST_OWNER_PASSWORD is not set. "
            "The owner account will NOT be auto-created. "
            "Set PUBCAST_OWNER_PASSWORD before first run."
        )
        return

    conn = _get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            hashed = get_password_hash(owner_pass)
            conn.execute(
                "INSERT OR IGNORE INTO users (username, hashed_password, role) VALUES (?, ?, 'owner')",
                (owner_name, hashed),
            )
            conn.commit()
            logger.info("userdb: owner account '%s' created", owner_name)
        else:
            logger.debug("userdb: users already exist, skipping owner seed")
    finally:
        conn.close()


def _sync_record_mod_action(room: str, operator: str, action: str, detail: str) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO mod_actions (room, operator, action, detail) VALUES (?, ?, ?, ?)",
            (room, operator, action, detail),
        )
        conn.commit()
    finally:
        conn.close()


def _sync_get_mod_actions(room: str, limit: int) -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT room, operator, action, detail, ts FROM mod_actions "
            "WHERE room = ? ORDER BY ts DESC LIMIT ?",
            (room, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Async public API
# ---------------------------------------------------------------------------

async def _in_thread(fn, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, fn, *args)


async def init_db() -> None:
    await _in_thread(_sync_init_db)




async def count_users() -> int:
    return await _in_thread(_sync_count_users)


async def create_owner_via_setup(username: str, password: str, email: str = "", display_name: str = "", discoverable: bool = False) -> bool:
    return await _in_thread(_sync_create_owner_via_setup, username, password, email, display_name, discoverable)


async def get_profile_by_username(username: str) -> Optional[Dict[str, Any]]:
    return await _in_thread(_sync_get_profile_by_username, username)


async def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
    return await _in_thread(_sync_get_profile, user_id)


async def list_profiles() -> List[Dict[str, Any]]:
    return await _in_thread(_sync_list_profiles)


async def update_profile(user_id: str, display_name: Optional[str] = None, email: Optional[str] = None, profile_details=None, expected_revision=None) -> Optional[Dict[str, Any]]:
    return await _in_thread(_sync_update_profile, user_id, display_name, email, profile_details, expected_revision)


def _sync_profile_photo(user_id: str, photo=None, expected_revision=None):
    import hashlib
    conn = _get_connection()
    try:
        if photo is None:
            row=conn.execute('SELECT photo_data FROM profiles WHERE user_id=?',(user_id,)).fetchone()
            return row[0] if row else None
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT profile_revision FROM profiles WHERE user_id=?',(user_id,)).fetchone()
        if row is None:
            raise ValueError('Profile not found')
        if expected_revision is not None and expected_revision != row[0]:
            raise ValueError('Profile changed in another window; reload it before saving')
        conn.execute('UPDATE profiles SET photo_data=?,photo_sha256=?,profile_revision=profile_revision+1 WHERE user_id=?',
                     (photo,hashlib.sha256(photo).hexdigest(),user_id))
        conn.commit()
    finally:
        conn.close()
    return _sync_get_profile(user_id)


async def profile_photo(user_id: str, photo=None, expected_revision=None):
    return await _in_thread(_sync_profile_photo,user_id,photo,expected_revision)


async def create_member(username: str, password: str, role: str, display_name: str = "", email: str = "") -> Optional[str]:
    return await _in_thread(_sync_create_member, username, password, role, display_name, email)


async def update_password_hash(username: str, hashed_password: str) -> bool:
    return await _in_thread(_sync_update_password_hash, username, hashed_password)


async def get_user(username: str) -> Optional[Dict[str, Any]]:
    return await _in_thread(_sync_get_user, username)


async def create_user(username: str, password: str, role: str = "guest") -> bool:
    return await _in_thread(_sync_create_user, username, password, role)


async def create_owner_if_not_exists() -> None:
    await _in_thread(_sync_create_owner_if_not_exists)


async def record_mod_action(room: str, operator: str, action: str, detail: str = "") -> None:
    await _in_thread(_sync_record_mod_action, room, operator, action, detail)


async def get_mod_actions(room: str, limit: int = 100) -> List[Dict[str, Any]]:
    return await _in_thread(_sync_get_mod_actions, room, limit)


# ---------------------------------------------------------------------------
# v6 additions — user management (WIRING_COMPLETE)
# ---------------------------------------------------------------------------

def _sync_get_all_users() -> List[Dict[str, Any]]:
    """Return all users sorted by created_at. Owner only."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT username, role, created_at FROM users ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _sync_update_user_role(username: str, new_role: str) -> Optional[str]:
    """
    Update a user's role. Returns the previous role, or None if user not found.
    Raises ValueError if the role is not a known role.
    """
    valid_roles = {"guest", "mod", "owner"}
    if new_role not in valid_roles:
        raise ValueError(f"Invalid role '{new_role}'. Must be one of: {valid_roles}")
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT role FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not row:
            return None
        old_role = row["role"]
        conn.execute(
            "UPDATE users SET role = ? WHERE username = ?",
            (new_role, username),
        )
        conn.commit()
        logger.info("userdb: role change for '%s': %s → %s", username, old_role, new_role)
        return old_role
    finally:
        conn.close()


def record_mod_action_sync(room: str, operator: str, action: str, detail: str = "") -> None:
    """Synchronous wrapper for record_mod_action — usable outside async context."""
    _sync_record_mod_action(room, operator, action, detail)


# Async wrappers for the new sync functions

async def get_all_users() -> List[Dict[str, Any]]:
    """Return all users. Caller should enforce owner-only access."""
    return await _in_thread(_sync_get_all_users)


async def update_user_role(username: str, new_role: str) -> Optional[str]:
    """
    Update user role. Returns the old role string, or None if user not found.
    Raises ValueError on invalid role.
    """
    return await _in_thread(_sync_update_user_role, username, new_role)
