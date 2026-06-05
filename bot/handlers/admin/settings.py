import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.middlewares.auth_check import admin_only
from bot.models.settings_model import get_setting, set_setting

logger = logging.getLogger(__name__)

@admin_only
async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Load stats
    cost_sms = await get_setting("cost_send_sms", 10)
    cost_recv = await get_setting("cost_receive_sms", 5)
    cost_panel = await get_setting("cost_add_panel", 20)
    cost_vip = await get_setting("cost_create_bot", 500)
    ref_pts = await get_setting("points_per_referral", 50)
    
    text = (
        "⚙️ **System Configuration**\n\n"
        "Here you can view the active limits and costs. "
        "Edit functionality can be added in future updates by connecting ConversationHandlers to these buttons."
    )
    
    keyboard = [
        [InlineKeyboardButton(f"Send SMS Cost ({cost_sms})", callback_data="admset_noop")],
        [InlineKeyboardButton(f"Recv SMS Cost ({cost_recv})", callback_data="admset_noop")],
        [InlineKeyboardButton(f"Add Panel Cost ({cost_panel})", callback_data="admset_noop")],
        [InlineKeyboardButton(f"Clone Cost ({cost_vip})", callback_data="admset_noop")],
        [InlineKeyboardButton(f"Ref Reward ({ref_pts})", callback_data="admset_noop")],
        [InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
