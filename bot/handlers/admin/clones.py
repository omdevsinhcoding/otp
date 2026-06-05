import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.middlewares.auth_check import admin_only
from bot.database import db

logger = logging.getLogger(__name__)

@admin_only
async def clones_list_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not db.pool:
         return
         
    async with db.pool.acquire() as conn:
        clones = await conn.fetch("SELECT id, owner_telegram_id, bot_username, is_active, expires_at FROM clone_bots ORDER BY id DESC LIMIT 10")
        
    if not clones:
        await query.edit_message_text(
            "🤖 **Clone Bots Management**\n\nNo clone bots found in system.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]])
        )
        return
        
    text = "🤖 **Clone Bots Management** (Top 10)\n\n"
    keyboard = []
    
    for c in clones:
        status = "🟢" if c['is_active'] else "🔴"
        text += f"{status} `@{c['bot_username']}` (Owner: `{c['owner_telegram_id']}`)\n"
        
        btn_text = f"{status} @{c['bot_username']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"admclone_{c['id']}")])
        
    keyboard.append([InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@admin_only
async def clone_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    try:
        clone_id = int(data.split("_")[1])
    except:
        return
        
    async with db.pool.acquire() as conn:
        clone = await conn.fetchrow("SELECT * FROM clone_bots WHERE id = $1", clone_id)
        
    if not clone:
        await query.edit_message_text("Not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_clones")]]))
        return
        
    status = "🟢 Active" if clone['is_active'] else ("🔴 Expired/Stopped" if clone['expires_at'].timestamp() < __import__("time").time() else "⏸️ Stopped")
    
    text = (
        f"🤖 **Clone Details:** `@{clone['bot_username']}`\n\n"
        f"ID: `{clone['id']}`\n"
        f"Owner UID: `{clone['owner_telegram_id']}`\n"
        f"Status: {status}\n"
        f"Expires: `{clone['expires_at'].strftime('%Y-%m-%d %H:%M')}`\n"
    )
    
    run_btn = "🛑 Force Stop" if clone['is_active'] else "▶️ Force Restart"
    run_btn_call = f"admclstop_{clone_id}" if clone['is_active'] else f"admclstart_{clone_id}"
    
    keyboard = [
        [InlineKeyboardButton(run_btn, callback_data=run_btn_call)],
        [InlineKeyboardButton("🗑️ Delete Clone", callback_data=f"admclonerman_{clone_id}")],
        [InlineKeyboardButton("⬅️ Back list", callback_data="adm_clones"), InlineKeyboardButton("⬅️ Admin Menu", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@admin_only
async def clone_run_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    from bot.services.clone_bot_manager import clone_manager
    
    try:
        clone_id = int(data.split("_")[1])
    except:
        return
        
    if data.startswith("admclstop_"):
        await db.pool.execute("UPDATE clone_bots SET is_active = FALSE WHERE id = $1", clone_id)
        await clone_manager.stop_clone(clone_id)
        await query.answer("Clone stopped.", show_alert=True)
        
    elif data.startswith("admclstart_"):
        await db.pool.execute("UPDATE clone_bots SET is_active = TRUE WHERE id = $1", clone_id)
        token = await db.pool.fetchval("SELECT bot_token FROM clone_bots WHERE id = $1", clone_id)
        from bot.utils.crypto_helpers import decrypt_token
        try:
            decrypted = decrypt_token(token)
            await clone_manager.start_clone(clone_id, decrypted)
            await query.answer("Clone started.", show_alert=True)
        except Exception:
            await query.answer("Failed to decrypt token.", show_alert=True)
        
    elif data.startswith("admclonerman_"):
        await db.pool.execute("DELETE FROM clone_bots WHERE id = $1", clone_id)
        await clone_manager.stop_clone(clone_id)
        await query.answer("Clone deleted.", show_alert=True)
        await clones_list_menu(update, context)
        return
        
    # Refresh
    query.data = f"admclone_{clone_id}"
    await clone_details(update, context)
