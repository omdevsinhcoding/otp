import logging
from bot.database import db

logger = logging.getLogger(__name__)

async def track_new_referral(referrer_id: int, referred_id: int, points_to_award: int) -> bool:
    """Inserts a referral tracking link without awarding points immediately (points wait for Force Join)."""
    if not db.pool:
        return False
    try:
        async with db.pool.acquire() as conn:
            # Check if this user was already referred
            exists = await conn.fetchval(
                "SELECT id FROM referrals WHERE referred_telegram_id = $1",
                referred_id
            )
            if exists:
                return False
                
            await conn.execute(
                """INSERT INTO referrals (referrer_telegram_id, referred_telegram_id, points_amount, points_awarded) 
                   VALUES ($1, $2, $3, FALSE)""",
                referrer_id, referred_id, points_to_award
            )
            return True
    except Exception as e:
        logger.error(f"Error tracking referral relationship: {e}")
        return False

async def finalize_referral_points(referred_id: int) -> tuple:
    """
    Called upon successful Force Join validation or direct register.
    Awards the pending points to the referrer, outputs (points_awarded_any, referrer_telegram_id, amount).
    """
    if not db.pool:
        return False, 0, 0
    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT referrer_telegram_id, points_amount, points_awarded FROM referrals WHERE referred_telegram_id = $1",
                referred_id
            )
            if not row or row['points_awarded']:
                return False, 0, 0
                
            ref_id = row['referrer_telegram_id']
            pts = row['points_amount']
            
            # Update referral record and award points to key user A
            await conn.execute("UPDATE referrals SET points_awarded = TRUE WHERE referred_telegram_id = $1", referred_id)
            await conn.execute("UPDATE users SET points = points + $1 WHERE telegram_id = $2", pts, ref_id)
            
            return True, ref_id, pts
    except Exception as e:
        logger.error(f"Error finalizing referral points: {e}")
        return False, 0, 0
