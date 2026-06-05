from telegram import Update
from telegram.ext import ContextTypes
from bot.middlewares.ban_check import ban_check
from bot.middlewares.points_check import points_required
from bot.database import db

# According to your prompt Section 3 & 6 mappings
@ban_check
@points_required(cost_setting="cost_send_sms")
async def send_sms_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 1 of Send SMS Flow: Triggered when user presses "📨 Send SMS"
    """
    user_id = update.effective_user.id
    
    # Setup Device Keyboard from Firebase
    panel_url = context.user_data.get("active_panel")
    if not panel_url:
        await update.callback_query.answer("Pehle ek Firebase Panel select/add karo!", show_alert=True)
        return
        
    await update.callback_query.edit_message_text(
        "Kaunsa device select karo? Fetching active devices..."
    )
    # Next step will be routed to select_device.py
    # return AWAITING_DEVICE
