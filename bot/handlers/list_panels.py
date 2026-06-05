from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.models.panel_model import get_user_panels, delete_panel_by_id

async def my_panels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Renders user's panels list in Postgres. Each shows status indicators and action paths.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    panels = await get_user_panels(user_id)
    active_panel = context.user_data.get("active_panel")
    
    if not panels:
        keyboard = [[InlineKeyboardButton("➕ Add New Panel", callback_data="add_panel")]]
        await query.edit_message_text(
            "⚠️ **No Panels Found!**\n\nYou haven't registered any Firebase Realtime Databases yet.\n"
            "Press below to connect your first board.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    text = "🤖 **Your Connected Firebase Boards**\n\nClick on any database url below to set it as your active commanding panel:\n\n"
    keyboard = []
    
    for p in panels:
        lbl = p['label'] or p['firebase_url'].split('//')[-1].split('.')[0]
        status_dot = "🟢" if p['is_valid'] else "🔴"
        select_indicator = " ⭐ [ACTIVE]" if active_panel == p['firebase_url'] else ""
        
        # Show each panel as button
        keyboard.append([InlineKeyboardButton(
            f"{status_dot} {lbl}{select_indicator}",
            callback_data=f"selpanel_{p['id']}"
        )])
        
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_panel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sets the selected panel as active and shows detailed options (like delete).
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    panel_id = int(query.data.split("_")[1])
    
    panels = await get_user_panels(user_id)
    selected = next((p for p in panels if p['id'] == panel_id), None)
    
    if not selected:
        await query.edit_message_text("Panel not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="my_panels")]]))
        return
        
    # Save selected panel to user state
    context.user_data["active_panel"] = selected["firebase_url"]
    
    text = (
        f"⭐️ **Panel Configured As Active Default!**\n\n"
        f"🏷️ **Label:** `{selected['label']}`\n"
        f"🔗 **URL:** `{selected['firebase_url']}`\n"
        f"🩺 **Cached Status:** `{'Operational 🟢' if selected['is_valid'] else 'Broken/Unauth 🔴'}`\n\n"
        f"All subsequent commands (Custom Send SMS, OTP Readings, Keep-Alive queries) will target this RTDB environment."
    )
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Delete Panel Project", callback_data=f"delpanel_{panel_id}")],
        [InlineKeyboardButton("🔄 Re-Analyze Schema", callback_data="my_panels")],
        [InlineKeyboardButton("⬅️ Back to List", callback_data="my_panels")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_panel_deletion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Deletes the elected board.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    panel_id = int(query.data.split("_")[1])
    
    # Remove from local active default context if it matches
    panels = await get_user_panels(user_id)
    selected = next((p for p in panels if p['id'] == panel_id), None)
    if selected and context.user_data.get("active_panel") == selected["firebase_url"]:
        context.user_data.pop("active_panel", None)
        
    await delete_panel_by_id(panel_id, user_id)
    await query.answer("🗑️ Panel references dropped successfully.", show_alert=True)
    await my_panels_menu(update, context)
