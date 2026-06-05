from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from bot.models.user_model import get_user

def ban_check(func):
    """
    Middleware decorator that prevents banned users from triggering bot commands 
    or button interactions. Queries ban status directly from Postgres records.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        user_record = await get_user(user_id)
        
        if user_record and user_record.get('is_banned', False):
            ban_reason = user_record.get('ban_reason') or 'No reason specified.'
            text = f"🚫 **Access Denied!**\n\nYou have been banned from this system by the Supreme Admin.\nReason: {ban_reason}"
            
            if update.callback_query:
                await update.callback_query.answer("⚠️ You are banned!", show_alert=True)
                await update.callback_query.message.reply_text(text)
            else:
                await update.message.reply_text(text)
            return
            
        return await func(update, context, *args, **kwargs)
    return wrapper
