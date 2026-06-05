import logging
from datetime import datetime, timedelta
from bot.database import db

logger = logging.getLogger(__name__)

async def get_user(telegram_id: int) -> dict:
    if not db.pool:
        return {}
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
            return dict(row) if row else {}
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return {}

async def create_user_if_not_exists(telegram_id: int, username: str, first_name: str, referred_by: int = None) -> bool:
    if not db.pool:
        return False
    try:
        async with db.pool.acquire() as conn:
            # Check if user already exists
            existing = await conn.fetchval("SELECT id FROM users WHERE telegram_id = $1", telegram_id)
            if existing:
                return False

            # Create User
            await conn.execute(
                """INSERT INTO users (telegram_id, username, first_name, referred_by, points, created_at)
                   VALUES ($1, $2, $3, $4, 0, NOW())""",
                telegram_id, username, first_name, referred_by
            )
            return True
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        return False

async def update_user_points(telegram_id: int, points_diff: int) -> int:
    """Adds or takes away points for a given user. Returns their new point balance."""
    if not db.pool:
        return 0
    try:
        async with db.pool.acquire() as conn:
            # Prevent negative points
            if points_diff < 0:
                current = await conn.fetchval("SELECT points FROM users WHERE telegram_id = $1", telegram_id)
                if current is None or current < abs(points_diff):
                    return None
                    
            new_pts = await conn.fetchval(
                """UPDATE users SET points = points + $1 WHERE telegram_id = $2 RETURNING points""",
                points_diff, telegram_id
            )
            return new_pts or 0
    except Exception as e:
        logger.error(f"Error updating user points: {e}")
        return 0

async def set_user_ban_status(telegram_id: int, is_banned: bool, reason: str = None) -> bool:
    if not db.pool:
        return False
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_banned = $1, ban_reason = $2 WHERE telegram_id = $3",
                is_banned, reason, telegram_id
            )
            return True
    except Exception as e:
        logger.error(f"Error setting ban for user: {e}")
        return False

async def purchase_vip(telegram_id: int, duration_days: int) -> bool:
    """Sets VIP status and updates expiry date from current time."""
    if not db.pool:
        return False
    try:
        async with db.pool.acquire() as conn:
            expiry = datetime.now() + timedelta(days=duration_days)
            await conn.execute(
                "UPDATE users SET is_vip = TRUE, vip_expires_at = $1 WHERE telegram_id = $2",
                expiry, telegram_id
            )
            return True
    except Exception as e:
        logger.error(f"Error purchasing VIP: {e}")
        return False

async def search_users(query: str) -> list:
    if not db.pool:
        return []
    try:
        async with db.pool.acquire() as conn:
            # Search by ID or Username wildcard
            rows = await conn.fetch(
                """SELECT * FROM users WHERE CAST(telegram_id AS TEXT) = $1 
                   OR LOWER(username) LIKE LOWER($2) ORDER BY created_at DESC LIMIT 50""",
                query, f"%{query}%"
            )
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Searching users error: {e}")
        return []
