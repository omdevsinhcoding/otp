import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import time

logger = logging.getLogger(__name__)

# Very simple in-memory store for rate limiting
# Mapping chat_id -> timestamp of last command
_user_last_action = {}

def rate_limit(cooldown_seconds: int = 1):
    """
    Rate limiting decorator to prevent spam.
    Ensures that user waits at least `cooldown_seconds` before calling the command again.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = None
            if update.message:
                user_id = update.message.from_user.id
            elif update.callback_query:
                user_id = update.callback_query.from_user.id
                
            if user_id:
                now = time.time()
                last_time = _user_last_action.get(user_id, 0)
                if now - last_time < cooldown_seconds:
                    wait_time = int(cooldown_seconds - (now - last_time))
                    msg = f"⏳ **Slow down!**\nPlease wait {wait_time} seconds before using this."
                    if update.callback_query:
                        await update.callback_query.answer(msg, show_alert=True)
                    else:
                        await update.message.reply_text(msg)
                    return # Block execution
                
                _user_last_action[user_id] = now
            
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
