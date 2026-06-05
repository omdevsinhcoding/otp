import json
import logging
import time
from bot.database import db

logger = logging.getLogger(__name__)

_cache = {}
_cache_ttl = 60  # seconds

async def get_setting(key: str, default=None):
    """Fetches a specific system configuration value by key, with 60 sec caching."""
    now = time.time()
    if key in _cache and (now - _cache[key]["time"]) < _cache_ttl:
        return _cache[key]["value"]
        
    if not db.pool:
        return default
    try:
        async with db.pool.acquire() as conn:
            # asyncpg returns parsed Python structures for JSONB
            # Ensure it works with json loads if it returns string
            val = await conn.fetchval("SELECT value FROM settings WHERE key = $1", key)
            
            if val is not None:
                if isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except:
                        pass
                _cache[key] = {"value": val, "time": now}
                return val
            return default
    except Exception as e:
        logger.error(f"Error reading setting {key}: {e}")
        return default

async def set_setting(key: str, value, admin_id: int = None) -> bool:
    """Updates or inserts a system configuration key mapping and invalidates cache."""
    if not db.pool:
        return False
    try:
        async with db.pool.acquire() as conn:
            val_to_store = json.dumps(value) if not isinstance(value, str) else value
            # In PostgreSQL JSONB, inserting a string representation of JSON is accepted.
            await conn.execute(
                """INSERT INTO settings (key, value, updated_by, updated_at) VALUES ($1, $2, $3, NOW())
                   ON CONFLICT (key) DO UPDATE SET value = $2, updated_by = $3, updated_at = NOW()""",
                key, val_to_store, admin_id
            )
            invalidate_cache(key)
            return True
    except Exception as e:
        logger.error(f"Error updating setting {key}: {e}")
        return False
        
def invalidate_cache(key: str = None):
    if key:
        _cache.pop(key, None)
    else:
        _cache.clear()
