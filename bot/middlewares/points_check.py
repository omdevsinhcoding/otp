from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from bot.models.user_model import get_user
from bot.models.settings_model import get_setting

def points_required(feature_key: str):
    """
    Decorator that checks user's points balance against pricing rules.
    If points system is active and user lacks required points, blocks execution
    and directs them to the refer & earn loop.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            # Check if points feature is globally toggled on
            pts_system_active = await get_setting("feature_points", True)
            if not pts_system_active:
                # Points are disabled by admin - all features are free of charge
                return await func(update, context, *args, **kwargs)
                
            user_record = await get_user(user_id)
            if not user_record:
                return # Block if untracked

            # VIP bypass point requirement
            if user_record.get("is_vip", False):
                return await func(update, context, *args, **kwargs)
                
            # Fetch cost limit dynamic settings
            feature_cost_key = f"cost_{feature_key}"
            points_cost = await get_setting(feature_cost_key, 0)
            
            current_points = user_record.get("points", 0)
            if current_points < points_cost:
                msg_text = (
                    f"⚠️ **Insufficient Points!**\n\n"
                    f"This feature requires **{points_cost} points**, but you only have **{current_points} points**.\n\n"
                    f"👥 Earning is simple! Click 'Refer & Earn' from the main menu, share your code, and receive points as soon as your friends join!"
                )
                if update.callback_query:
                    await update.callback_query.answer("⚠️ Insufficient Points!", show_alert=True)
                    # Optionally edit or send text
                    await update.callback_query.message.reply_text(msg_text)
                else:
                    await update.message.reply_text(msg_text)
                return
                
            # Let call proceed
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator
