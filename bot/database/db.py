import asyncpg
import logging
from config import DATABASE_URL

logger = logging.getLogger(__name__)
pool = None

async def init_db():
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
        logger.info("Database connection pool established.")
        await create_tables()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")

async def create_tables():
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        username VARCHAR(255),
        first_name VARCHAR(255),
        points INTEGER DEFAULT 0,
        is_vip BOOLEAN DEFAULT FALSE,
        vip_expires_at TIMESTAMP,
        is_banned BOOLEAN DEFAULT FALSE,
        ban_reason TEXT,
        referred_by BIGINT,
        force_join_completed BOOLEAN DEFAULT FALSE,
        panels_count INTEGER DEFAULT 0,
        clone_bots_count INTEGER DEFAULT 0,
        force_bot_limit INTEGER DEFAULT 1,
        last_active_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS clone_bots (
        id SERIAL PRIMARY KEY,
        owner_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
        bot_token TEXT NOT NULL,
        bot_username VARCHAR(255),
        is_active BOOLEAN DEFAULT TRUE,
        expires_at TIMESTAMP NOT NULL,
        total_users INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS panels (
        id SERIAL PRIMARY KEY,
        user_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
        firebase_url TEXT NOT NULL,
        label VARCHAR(255),
        is_valid BOOLEAN DEFAULT TRUE,
        last_checked_at TIMESTAMP,
        last_error TEXT,
        devices_count INTEGER DEFAULT 0,
        sms_count INTEGER DEFAULT 0,
        added_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS referrals (
        id SERIAL PRIMARY KEY,
        referrer_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
        referred_telegram_id BIGINT NOT NULL REFERENCES users(telegram_id),
        points_awarded BOOLEAN DEFAULT FALSE,
        points_amount INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS broadcasts (
        id SERIAL PRIMARY KEY,
        sent_by BIGINT NOT NULL,
        message_text TEXT NOT NULL,
        parse_mode VARCHAR(20) DEFAULT 'HTML',
        inline_buttons JSONB,
        total_sent INTEGER DEFAULT 0,
        total_failed INTEGER DEFAULT 0,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS system_logs (
        id SERIAL PRIMARY KEY,
        category VARCHAR(50) NOT NULL,
        action VARCHAR(255) NOT NULL,
        details JSONB,
        performed_by BIGINT,
        target_user BIGINT,
        ip_address VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS settings (
        key VARCHAR(255) PRIMARY KEY,
        value JSONB NOT NULL,
        updated_by BIGINT,
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS firebase_analysis (
        id SERIAL PRIMARY KEY,
        firebase_url TEXT NOT NULL,
        response_status INTEGER,
        response_type VARCHAR(50),
        data_structure JSONB,
        patterns_found JSONB,
        raw_response_preview TEXT,
        analyzed_at TIMESTAMP DEFAULT NOW()
    );
    """
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(schema)
            try:
                await conn.execute("ALTER TABLE users ADD COLUMN force_bot_limit INTEGER DEFAULT 1;")
            except Exception:
                pass
            # Seed default admin settings
            default_settings = [
                ('force_join_enabled', 'false'),
                ('force_join_channels', '[]'),
                ('points_per_referral', '50'),
                ('cost_send_sms', '10'),
                ('cost_receive_sms', '5'),
                ('cost_add_panel', '20'),
                ('cost_create_bot', '500'),
                ('vip_duration_days', '30'),
                ('max_panels_per_user', '5'),
                ('max_clones_per_user', '1'),
                ('polling_interval_seconds', '10'),
                ('system_enabled', 'true'),
                ('feature_send_sms', 'true'),
                ('feature_receive_sms', 'true'),
                ('feature_add_panel', 'true'),
                ('feature_clone_bot', 'true'),
                ('feature_referrals', 'true'),
                ('feature_points', 'true'),
                ('disclaimer_text', '""'),
                ('welcome_message', '"Welcome to the bot!"'),
                ('maintenance_mode', 'false'),
                ('admin_ids', '[123456789]')
            ]
            for key, val in default_settings:
                await conn.execute(
                    "INSERT INTO settings (key, value) VALUES ($1, $2::jsonb) ON CONFLICT (key) DO NOTHING",
                    key, val
                )

async def get_user(telegram_id: int):
    if not pool: return None
    async with pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM users WHERE telegram_id = $1', telegram_id)

async def create_user(telegram_id: int, username: str, first_name: str, referred_by: int = None):
    if not pool: return
    async with pool.acquire() as conn:
        await conn.execute(
            '''INSERT INTO users (telegram_id, username, first_name, referred_by)
               VALUES ($1, $2, $3, $4) ON CONFLICT (telegram_id) DO NOTHING''',
            telegram_id, username, first_name, referred_by
        )
