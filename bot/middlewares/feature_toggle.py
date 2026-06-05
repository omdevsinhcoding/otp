import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from functools import wraps
from bot.models.settings_model import get_setting

logger = logging.getLogger(__name__)

def feature_enabled(feature_key: str):
    """
    Decorator to check if a specific feature is enabled in system settings.
    Bypasses standard users if disabled, allowing Admins anyway.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Globals
            sys_enabled = await get_setting("system_enabled", True)
            
            # Check user role
            # If system is disabled, and user is not admin, stop them.
            # Usually we do role check first.
            from bot.config import ADMINS
            
            user_id = None
            if update.message:
                user_id = update.message.from_user.id
            elif update.callback_query:
                user_id = update.callback_query.from_user.id
                
            is_admin = user_id in ADMINS
            
            if not is_admin:
                if not sys_enabled:
                    msg = "🔧 **Bot under maintenance**\n\nThe entire system is temporarily disabled. Please check back later."
                    if update.callback_query:
                        await update.callback_query.edit_message_text(msg)
                    else:
                        await update.message.reply_text(msg)
                    return
                
                feat_enabled = await get_setting(feature_key, True)
                if not feat_enabled:
                    msg = "🚫 **Feature Disabled**\n\nThis feature is temporarily disabled by admin."
                    if update.callback_query:
                        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="back_to_menu")]]))
                    else:
                        await update.message.reply_text(msg)
                    return
                    
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
