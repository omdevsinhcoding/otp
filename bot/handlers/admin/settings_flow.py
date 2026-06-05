import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from bot.middlewares.auth_check import admin_only
from bot.models.settings_model import get_setting, set_setting

logger = logging.getLogger(__name__)

(AWAIT_PRICING, AWAIT_FJ_CHANNEL, AWAIT_FJ_REMOVE) = range(3)

@admin_only
async def settings_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    enabled_fj = await get_setting("force_join_enabled", False)
    channels = await get_setting("force_join_channels", [])
    ch_count = len(channels)
    status_fj = "🟢 ON" if enabled_fj else "🔴 OFF"

    cost_sms = await get_setting("cost_send_sms", 10)
    cost_recv = await get_setting("cost_receive_sms", 5)
    cost_panel = await get_setting("cost_add_panel", 20)
    cost_vip = await get_setting("cost_create_bot", 500)
    ref_pts = await get_setting("points_per_referral", 50)
    vip_dur = await get_setting("vip_duration_days", 30)
    max_bots = await get_setting("max_clones_per_user", 1)
    max_pan = await get_setting("max_panels_per_user", 5)
    poll_int = await get_setting("polling_interval_seconds", 10)

    text = (
        f"╔═════════════════════════════════════════╗\n"
        f"║              ⚙️ BOT SETTINGS           ║\n"
        f"╠═════════════════════════════════════════╣\n"
        f"║                                         ║\n"
        f"║  [📢 Force Join Settings]               ║\n"
        f"║     Channels: {ch_count} | Status: {status_fj}      ║\n"
        f"║                                         ║\n"
        f"║  [💰 Points & Pricing]                  ║\n"
        f"║     Ref: {ref_pts} | SMS Send: {cost_sms} | Recv: {cost_recv}     ║\n"
        f"║     Add Panel: {cost_panel} | Clone Bot: {cost_vip}       ║\n"
        f"║                                         ║\n"
        f"║  [📋 Limits & Timers]                   ║\n"
        f"║     Clone: {max_bots}/user | Panels: {max_pan}/user ║\n"
        f"║     VIP Dur: {vip_dur}d | Polling: {poll_int}s       ║\n"
        f"║                                         ║\n"
        f"╚═════════════════════════════════════════╝"
    )

    keyboard = [
        [InlineKeyboardButton("📢 Manage Force Join", callback_data="set_fj")],
        [InlineKeyboardButton("💰 Manage Pricing", callback_data="set_pricing")],
        [InlineKeyboardButton("📋 Manage Limits", callback_data="set_limits")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

@admin_only
async def fj_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    enabled_fj = await get_setting("force_join_enabled", False)
    channels = await get_setting("force_join_channels", [])
    
    status = "🟢 ENABLED" if enabled_fj else "🔴 DISABLED"
    text = f"📢 **Force Join Settings**\nStatus: {status}\n\nChannels:\n"
    
    for i, ch in enumerate(channels, 1):
        text += f"{i}. 📢 {ch.get('title', ch.get('username'))} ({ch.get('members_count', '??')} members)\n"
        
    if not channels:
        text += "No channels configured."

    keyboard = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="fj_add"),
         InlineKeyboardButton("🗑️ Remove Channel", callback_data="fj_remove")],
        [InlineKeyboardButton("🔄 Toggle ON/OFF", callback_data="fj_toggle")],
        [InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_settings")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
@admin_only
async def fj_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "fj_toggle":
        curr = await get_setting("force_join_enabled", False)
        await set_setting("force_join_enabled", not curr, admin_id=update.effective_user.id)
        return await fj_menu(update, context)
        
    elif data == "fj_add":
        await query.edit_message_text(
            "Send the **Channel ID** (e.g. @MyChannel or -100123...).\n"
            "⚠️ Bot MUST be admin in that channel before adding.\n\n"
            "Send /cancel to abort."
        )
        return AWAIT_FJ_CHANNEL
        
    elif data == "fj_remove":
        # simple inline remove
        channels = await get_setting("force_join_channels", [])
        if not channels:
            await query.answer("No channels to remove.", show_alert=True)
            return await fj_menu(update, context)
            
        keyboard = []
        for i, ch in enumerate(channels):
            keyboard.append([InlineKeyboardButton(f"❌ Remove {ch.get('title')}", callback_data=f"fj_rm_idx_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="set_fj")])
        await query.edit_message_text("Select channel to remove:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data.startswith("fj_rm_idx_"):
        idx = int(data.split("_")[-1])
        channels = await get_setting("force_join_channels", [])
        if idx < len(channels):
            removed = channels.pop(idx)
            await set_setting("force_join_channels", channels, admin_id=update.effective_user.id)
            if not channels:
                await set_setting("force_join_enabled", False)
            await query.answer(f"Removed {removed.get('title')}")
        return await fj_menu(update, context)
        
@admin_only
async def fj_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
        await settings_main_menu(update, context)
        return ConversationHandler.END
        
    chat_id = text
    try:
        chat = await context.bot.get_chat(chat_id)
        # Check bot is admin
        bot_member = await context.bot.get_chat_member(chat_id=chat.id, user_id=context.bot.id)
        if bot_member.status not in ["administrator", "creator"]:
            await update.message.reply_text("❌ The bot is not an admin in this channel. Make it admin and try again. /cancel to abort.")
            return AWAIT_FJ_CHANNEL
            
        # Get invite link
        invite_link = None
        if chat.username:
            invite_link = f"https://t.me/{chat.username}"
        else:
            try:
                invite_link = await context.bot.export_chat_invite_link(chat_id=chat.id)
            except Exception:
                invite_link = None
                
        # Count
        try:
            members_count = await context.bot.get_chat_member_count(chat.id)
        except:
            members_count = 0
            
        new_channel = {
            "id": chat.id,
            "username": f"@{chat.username}" if chat.username else None,
            "title": chat.title,
            "type": chat.type,
            "invite_link": invite_link,
            "members_count": members_count
        }
        
        channels = await get_setting("force_join_channels", [])
        # Check duplicate
        if any(c["id"] == chat.id for c in channels):
            await update.message.reply_text("⚠️ This channel is already in Force Join list. /cancel to abort.")
            return AWAIT_FJ_CHANNEL
            
        channels.append(new_channel)
        await set_setting("force_join_channels", channels, admin_id=update.effective_user.id)
        
        if len(channels) == 1:
            await set_setting("force_join_enabled", True, admin_id=update.effective_user.id)
            
        await update.message.reply_text(f"✅ Channel '{chat.title}' successfully added.")
        await settings_main_menu(update, context)
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching chat: {e}. Ensure ID is correct and bot is admin. Send another ID or /cancel.")
        return AWAIT_FJ_CHANNEL

@admin_only
async def pricing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cost_sms = await get_setting("cost_send_sms", 10)
    cost_recv = await get_setting("cost_receive_sms", 5)
    cost_panel = await get_setting("cost_add_panel", 20)
    cost_vip = await get_setting("cost_create_bot", 500)
    ref_pts = await get_setting("points_per_referral", 50)

    text = (
        "💰 **Pricing Settings**\n\n"
        "Select an item to change its value. "
    )
    keyboard = [
        [InlineKeyboardButton(f"Send SMS ({cost_sms})", callback_data="prc_cost_send_sms"),
         InlineKeyboardButton(f"Recv SMS ({cost_recv})", callback_data="prc_cost_receive_sms")],
        [InlineKeyboardButton(f"Add Panel ({cost_panel})", callback_data="prc_cost_add_panel"),
         InlineKeyboardButton(f"Clone Cost ({cost_vip})", callback_data="prc_cost_create_bot")],
        [InlineKeyboardButton(f"Referral ({ref_pts})", callback_data="prc_points_per_referral")],
        [InlineKeyboardButton("🔙 Back to Settings", callback_data="adm_settings")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@admin_only
async def pricing_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    key = query.data.split("prc_")[1]
    context.user_data["edit_setting_key"] = key
    
    current = await get_setting(key, 0)
    await query.edit_message_text(
        f"Please send the new value for `{key}`.\n"
        f"Current value: {current}\n\n"
        f"Type /cancel to abort."
    )
    return AWAIT_PRICING

@admin_only
async def save_pricing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
        await settings_main_menu(update, context)
        return ConversationHandler.END
        
    try:
        val = int(text)
        if val < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Invalid number. Please enter a valid non-negative integer or /cancel.")
        return AWAIT_PRICING
        
    key = context.user_data.get("edit_setting_key")
    if key:
        await set_setting(key, val, admin_id=update.effective_user.id)
        await update.message.reply_text(f"✅ Pricing `{key}` updated to {val}.")
        
    await settings_main_menu(update, context)
    return ConversationHandler.END
