import httpx
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from bot.models.user_model import get_user, update_user_points, purchase_vip
from bot.models.settings_model import get_setting
from bot.middlewares.ban_check import ban_check
from bot.middlewares.feature_toggle import feature_enabled
from bot.middlewares.rate_limit import rate_limit
from bot.database import db
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# State constants for clone creation conversation
ENTERING_TOKEN = 1

@ban_check
@feature_enabled("f_clone_bot")
@rate_limit(cooldown_seconds=10)
async def create_bot_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Kicks off Create Bot / VIP lifecycle check.
    """
    query = update.callback_query
    await query.answer()
    
    if context.bot_data.get("is_clone", False):
        await query.edit_message_text("🚫 Sub-clones cannot spawn additional bots. Master instance required.")
        return ConversationHandler.END
        
    user_id = query.from_user.id
    user_record = await get_user(user_id)
    if not user_record:
        return ConversationHandler.END

    is_vip = user_record.get("is_vip", False)
    vip_expires = user_record.get("vip_expires_at")
    
    # Check if VIP already expired
    if is_vip and vip_expires:
        if datetime.now() > vip_expires:
            # VIP Expired - set active=False
            if db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute("UPDATE users SET is_vip = FALSE WHERE telegram_id = $1", user_id)
                    await conn.execute("UPDATE clone_bots SET is_active = FALSE WHERE owner_telegram_id = $1", user_id)
            is_vip = False

    cost_vip = await get_setting("cost_create_bot", 500)
    current_pts = user_record.get("points", 0)

    if not is_vip:
        # Prompt VIP Purchase
        text = (
            f"👑 **VIP Clone Bot Terminal**\n\n"
            f"You do not possess VIP privileges currently.\n"
            f"Creating a personal cloned bot requires **{cost_vip} points** (30-day lease duration).\n\n"
            f"💰 **Your Balance:** `{current_pts} points`"
        )
        keyboard = []
        if current_pts >= cost_vip:
            keyboard.append([InlineKeyboardButton("⭐ Purchase VIP Status", callback_data="buy_vip")])
        else:
            keyboard.append([InlineKeyboardButton("👥 Get Points (Refer & Earn)", callback_data="refer")])
            
        keyboard.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
        
    # Check if they reached max limit (Scenario #9)
    max_clones = user_record.get("force_bot_limit")
    if not max_clones:
        max_clones = await get_setting("max_clones_per_user", 1)
        
    clone_count = 0
    if db.pool:
        async with db.pool.acquire() as conn:
             clone_count = await conn.fetchval(
                 "SELECT COUNT(*) FROM clone_bots WHERE owner_telegram_id = $1 AND is_active = TRUE",
                 user_id
             )
             
    if clone_count >= max_clones:
        await query.edit_message_text(
            f"🚫 **Limit Reached!**\n\nYou have already deployed **{clone_count}/{max_clones} active clone bots**.\n\n"
            f"You cannot create more at this moment.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="back_to_menu")]])
        )
        return ConversationHandler.END

    # Request Token from BotFather
    text = (
        f"🤖 **Deploy Cloned C2 Bot**\n\n"
        f"1. Open @BotFather in Telegram.\n"
        f"2. Use `/newbot` command to create a brand new bot.\n"
        f"3. Copy the HTTP API **Access Token** provided.\n"
        f"4. **Paste and send the Token** down below:\n\n"
        f"_Our engine will analyze, connect, and instantly spawn your bot template!_"
    )
    await query.edit_message_text(text)
    return ENTERING_TOKEN

async def buy_vip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Performs VIP billing logic.
    """
    query = update.callback_query
    await query.answer()
    
    if context.bot_data.get("is_clone", False):
        return
        
    user_id = query.from_user.id
    user_record = await get_user(user_id)
    cost_vip = await get_setting("cost_create_bot", 500)
    duration_days = await get_setting("vip_duration_days", 30)
    
    if user_record.get("points", 0) < cost_vip:
        await query.answer("❌ Insufficient points balance!", show_alert=True)
        return
        
    # Deduct points and purchase
    await update_user_points(user_id, -cost_vip)
    await purchase_vip(user_id, duration_days)
    
    await query.answer("🎉 VIP Privileges Unlocked!", show_alert=True)
    await create_bot_menu(update, context)

async def process_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Validates token via Telegram getMe and launches clone rows.
    """
    user_id = update.effective_user.id
    token = update.message.text.strip()
    
    msg = await update.message.reply_text("🔄 Validating Token parameters with Telegram API...")
    
    # Call Telegram API
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(f"https://api.telegram.org/bot{token}/getMe")
            if res.status_code == 200:
                data = res.json()
                if not data.get("ok"):
                    await msg.edit_text("❌ **Invalid Token!**\n\nTelegram BotFather did not recognize this Token. Make sure you copied it correctly.")
                    return ConversationHandler.END
                    
                bot_username = data["result"]["username"]
                bot_name = data["result"]["first_name"]
            else:
                await msg.edit_text("❌ **Invalid Token!**\n\nAPI authorization failed. Sahi token paste karo.")
                return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error checking bot token: {e}")
        await msg.edit_text("❌ API timeout. Please verify network or try again shortly.")
        return ConversationHandler.END

    duration_days = await get_setting("vip_duration_days", 30)
    expiry = datetime.now() + timedelta(days=duration_days)

    from bot.utils.crypto_helpers import encrypt_token
    secure_token = encrypt_token(token)

    # Insert into clone_bots table in Neon PG
    if db.pool:
        try:
            async with db.pool.acquire() as conn:
                clone_id = await conn.fetchval(
                    """INSERT INTO clone_bots (owner_telegram_id, bot_token, bot_username, is_active, expires_at)
                       VALUES ($1, $2, $3, TRUE, $4) RETURNING id""",
                    user_id, secure_token, bot_username, expiry
                )
            
            # Start the bot dynamically
            from bot.services.clone_bot_manager import clone_manager
            await clone_manager.start_clone(clone_id, token)
            
        except Exception as e:
            logger.error(f"Error creating clone bot row: {e}")
            await msg.edit_text("❌ Database error configuring clone instance. Please contact admins.")
            return ConversationHandler.END

    success_text = (
        f"🚀 **Bot Successfully Created!**\n\n"
        f"🤖 **Bot Handle:** @{bot_username}\n"
        f"🏷️ **First Name:** `{bot_name}`\n"
        f"⏰ **Expires At:** `{expiry.strftime('%Y-%m-%d')}`\n\n"
        f"Your custom environment has been deployed on our European cloud hosting! Share the username with your users to start tracking devices.\n\n"
        f"🎈 _Features available: Admin panel, broad settings, logs, referrals, and statistics._"
    )
    await msg.edit_text(success_text)
    
    # Notify admin
    from bot.config import ADMINS
    if ADMINS:
        try:
            admin_msg = f"🔔 **New Clone Bot Deployed!**\n\n👤 Owner: `{user_id}`\n🤖 Bot: @{bot_username}"
            from telegram import Bot
            from bot.config import BOT_TOKEN
            b = Bot(BOT_TOKEN)
            for a_id in ADMINS:
                await b.send_message(chat_id=a_id, text=admin_msg)
        except Exception:
            pass
            
    return ConversationHandler.END
