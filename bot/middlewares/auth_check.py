from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from bot.config import SUPREME_ADMIN_ID
from bot.models.settings_model import get_setting

def admin_only(func):
    """
    Blocks command execution unless the sender ID matches SUPREME_ADMIN_ID 
    or belongs inside the admin_ids list in database settings.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id == SUPREME_ADMIN_ID:
            return await func(update, context, *args, **kwargs)
            
        # Check sub-admins config in neon settings
        admin_list = await get_setting("admin_ids", [])
        if user_id in admin_list:
            return await func(update, context, *args, **kwargs)

        if update.callback_query:
            await update.callback_query.answer("🛡️ This area is restricted to Authorized Admins only.", show_alert=True)
        else:
            await update.message.reply_text("🚫 This area is restricted to Authorized Admins only.")
        return
    return wrapper
