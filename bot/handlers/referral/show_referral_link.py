from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.models.user_model import get_user
from bot.models.settings_model import get_setting
from bot.database import db

from bot.middlewares.feature_toggle import feature_enabled

@feature_enabled("f_referral")
async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Renders 'Refer & Earn' stats, current referral count, and gives the personalized referral link.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_record = await get_user(user_id)
    pts_per_ref = await get_setting("points_per_referral", 50)
    
    # Query invited user counts from Neon PG
    invited_count = 0
    if db.pool:
         async with db.pool.acquire() as conn:
             invited_count = await conn.fetchval(
                 "SELECT COUNT(*) FROM referrals WHERE referrer_telegram_id = $1",
                 user_id
             )
             
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    msg_text = (
        f"👥 **Refer & Earn Program**\n\n"
        f"Share your link with friends to get points! Once they start the bot and join mandatory channels, you earn credits immediately.\n\n"
        f"💰 **Points per successful referral:** `{pts_per_ref} points`\n"
        f"📊 **Total referred list count:** `{invited_count} friends`\n\n"
        f"🚀 **Your unique Referral Link:**\n`{ref_link}`\n\n"
        f"_Tap link to copy it instantly format._"
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]
    await query.edit_message_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard))
