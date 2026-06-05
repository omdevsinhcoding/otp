import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.models.user_model import get_user
from bot.models.settings_model import get_setting
from bot.models.referral_model import finalize_referral_points
from bot.database import db
from bot.services.force_join_verifier import verify_all_channels

logger = logging.getLogger(__name__)

async def verify_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Triggers when user clicks 'Verify Join'. Re-checks memberships.
    If joined, updates database node and unlocks active menu.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_record = await get_user(user_id)
    if not user_record:
        return
        
    check_result = await verify_all_channels(context.bot, user_id)
            
    if not check_result["all_joined"]:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = []
        for ch in check_result["results"]:
            status = "✅" if ch["joined"] else "❌"
            title = ch.get("title", ch.get("username", "Channel"))
            invite_link = ch.get("invite_link")
            if not invite_link and ch.get("username"):
                invite_link = f"https://t.me/{ch.get('username').lstrip('@')}"
            if not ch["joined"]:
                keyboard.append([InlineKeyboardButton(f"{status} Join {title}", url=invite_link or "https://t.me")])
            else:
                keyboard.append([InlineKeyboardButton(f"{status} {title}", callback_data="noop")])
            
        keyboard.append([InlineKeyboardButton("✅ VERIFY — I Have Joined", callback_data="verify_join")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"╔═════════════════════════════════════════╗\n"
            f"║         🔒 FORCE JOIN REQUIRED        ║\n"
            f"╠═════════════════════════════════════════╣\n"
            f"║                                         ║\n"
            f"║  You still haven't joined all required   ║\n"
            f"║  channels. Please join the remaining:    ║\n"
            f"║                                         ║\n"
            f"╚═════════════════════════════════════════╝"
        )
        await query.edit_message_text(text, reply_markup=reply_markup)
        return
        
    # Standardise completion state in database
    if db.pool:
        async with db.pool.acquire() as conn:
            await conn.execute("UPDATE users SET force_join_completed = TRUE WHERE telegram_id = $1", user_id)
            
    # Notify Referrer with points!
    awarded, referrer, amount = await finalize_referral_points(user_id)
    if awarded:
        try:
            await context.bot.send_message(
                chat_id=referrer,
                text=f"🎁 **Referral Registered!**\n\nYour friend joined and successfully verified join. You earned **{amount} points**!"
            )
        except Exception as e:
            logger.warning(f"Failed to msg referrer {referrer}: {e}")
            
    # Success, show menu
    await query.edit_message_text("✅ Verification successful! Loading main menu...")
    
    # Reload local cache
    updated_user = await get_user(user_id)
    from bot.handlers.start import show_main_menu_message
    await show_main_menu_message(update, context, updated_user)
