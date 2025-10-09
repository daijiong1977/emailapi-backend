import os
import sqlite3
import secrets
import hashlib
import time
from typing import Optional, List, Dict


def _connect(db_path: str):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str):
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    conn = _connect(db_path)
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                secret_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                revoked_at INTEGER
            )
            """
        )
    conn.close()


def _hash_secret(secret: str, salt: str) -> str:
    return hashlib.sha256((salt + secret).encode('utf-8')).hexdigest()


def create_key(db_path: str, username: str) -> str:
    """Create a new API key for a user. Returns the client key string 'key_id.secret'."""
    key_id = secrets.token_hex(8)
    secret = secrets.token_hex(24)
    salt = secrets.token_hex(8)
    secret_hash = _hash_secret(secret, salt)
    now = int(time.time())
    conn = _connect(db_path)
    with conn:
        conn.execute(
            "INSERT INTO api_keys (key_id, username, secret_hash, salt, created_at, revoked_at) VALUES (?, ?, ?, ?, ?, NULL)",
            (key_id, username, secret_hash, salt, now),
        )
    conn.close()
    return f"{key_id}.{secret}"


def revoke_key(db_path: str, key_id: str) -> bool:
    conn = _connect(db_path)
    with conn:
        cur = conn.execute("UPDATE api_keys SET revoked_at=? WHERE key_id=? AND revoked_at IS NULL", (int(time.time()), key_id))
        changed = cur.rowcount
    conn.close()
    return changed > 0


def list_keys(db_path: str) -> List[Dict]:
    conn = _connect(db_path)
    cur = conn.execute("SELECT key_id, username, created_at, revoked_at FROM api_keys ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def verify_key(db_path: str, client_key: str) -> Optional[str]:
    """Verify a client key 'key_id.secret'. Returns username if valid, else None."""
    if '.' not in client_key:
        return None
    key_id, secret = client_key.split('.', 1)
    conn = _connect(db_path)
    cur = conn.execute("SELECT username, secret_hash, salt, revoked_at FROM api_keys WHERE key_id=?", (key_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if row["revoked_at"] is not None:
        return None
    calc = _hash_secret(secret, row["salt"]) 
    if secrets.compare_digest(calc, row["secret_hash"]):
        return row["username"]
    return None
