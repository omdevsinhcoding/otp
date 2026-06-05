import logging
from bot.database import db

logger = logging.getLogger(__name__)

async def get_user_panels(user_id: int) -> list:
    """Fetches all panel URLs registered by a specific Telegram User ID."""
    if not db.pool:
        return []
    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, firebase_url, label, is_valid FROM panels WHERE user_telegram_id = $1 ORDER BY added_at DESC",
                user_id
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching user panels: {e}")
        return []

async def add_panel(user_id: int, url: str, label: str = None) -> bool:
    """Inserts a new verified Firebase RTDB URL for a user."""
    if not db.pool:
        return False
    try:
        async with db.pool.acquire() as conn:
            # Check for duplicate
            dup = await conn.fetchrow(
                "SELECT id FROM panels WHERE user_telegram_id = $1 AND firebase_url = $2",
                user_id, url
            )
            if dup:
                return False  # Already exists
                
            await conn.execute(
                "INSERT INTO panels (user_telegram_id, firebase_url, label, is_valid) VALUES ($1, $2, $3, TRUE)",
                user_id, url, label or f"Panel {url.split('//')[-1].split('.')[0]}"
            )
            return True
    except Exception as e:
        logger.error(f"Error inserting user panel: {e}")
        return False

async def delete_panel_by_id(panel_id: int, user_id: int) -> bool:
    """Deletes a panel from user's account."""
    if not db.pool:
        return False
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM panels WHERE id = $1 AND user_telegram_id = $2",
                panel_id, user_id
            )
            return True
    except Exception as e:
        logger.error(f"Error deleting panel: {e}")
        return False
