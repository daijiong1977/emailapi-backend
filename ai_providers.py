"""AI provider management for proxy service."""

import sqlite3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

AI_DB_PATH = os.getenv('AI_PROVIDERS_DB', 'ai_providers.db')


def init_ai_db():
    """Initialize AI providers database."""
    conn = sqlite3.connect(AI_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            provider_type TEXT NOT NULL,
            api_key TEXT NOT NULL,
            base_url TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()


def add_ai_provider(name: str, provider_type: str, api_key: str, base_url: Optional[str] = None, enabled: bool = True) -> bool:
    """Add or update an AI provider."""
    conn = sqlite3.connect(AI_DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    
    try:
        # Check if exists
        cursor.execute("SELECT id FROM ai_providers WHERE name = ?", (name,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing
            cursor.execute("""
                UPDATE ai_providers 
                SET provider_type = ?, api_key = ?, base_url = ?, enabled = ?, updated_at = ?
                WHERE name = ?
            """, (provider_type, api_key, base_url, 1 if enabled else 0, now, name))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO ai_providers (name, provider_type, api_key, base_url, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, provider_type, api_key, base_url, 1 if enabled else 0, now, now))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding AI provider: {e}")
        return False
    finally:
        conn.close()


def get_enabled_provider() -> Optional[Dict[str, Any]]:
    """Get the currently enabled AI provider."""
    conn = sqlite3.connect(AI_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, provider_type, api_key, base_url, enabled, created_at, updated_at
        FROM ai_providers
        WHERE enabled = 1
        ORDER BY updated_at DESC
        LIMIT 1
    """)
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def list_ai_providers(include_keys: bool = False) -> List[Dict[str, Any]]:
    """List all AI providers."""
    conn = sqlite3.connect(AI_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, provider_type, api_key, base_url, enabled, created_at, updated_at
        FROM ai_providers
        ORDER BY name
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    providers = []
    for row in rows:
        provider = dict(row)
        if not include_keys:
            # Mask API key
            provider['api_key'] = '***' + provider['api_key'][-4:] if len(provider['api_key']) > 4 else '****'
        providers.append(provider)
    
    return providers


def toggle_provider(name: str, enabled: bool) -> bool:
    """Enable or disable a provider."""
    conn = sqlite3.connect(AI_DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    
    try:
        # If enabling this provider, disable all others
        if enabled:
            cursor.execute("UPDATE ai_providers SET enabled = 0")
        
        cursor.execute("""
            UPDATE ai_providers
            SET enabled = ?, updated_at = ?
            WHERE name = ?
        """, (1 if enabled else 0, now, name))
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error toggling provider: {e}")
        return False
    finally:
        conn.close()


def delete_provider(name: str) -> bool:
    """Delete an AI provider."""
    conn = sqlite3.connect(AI_DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM ai_providers WHERE name = ?", (name,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting provider: {e}")
        return False
    finally:
        conn.close()


# Initialize database on module load
init_ai_db()
