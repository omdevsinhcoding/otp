import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from bot.middlewares.auth_check import admin_only
from bot.database import db

logger = logging.getLogger(__name__)

AWAITING_SEARCH = 1

@admin_only
async def search_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔍 **Search User**\n\n"
        "Send the **Telegram ID** of the user you want to manage.\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_menu")]])
    )
    return AWAITING_SEARCH

@admin_only
async def process_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "/cancel":
         await update.message.reply_text("Canceled.")
         return ConversationHandler.END
         
    user_id = None
    user = None
    
    async with db.pool.acquire() as conn:
        if text.isdigit():
            user_id = int(text)
            user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)
        else:
            username = text.lstrip("@")
            user = await conn.fetchrow("SELECT * FROM users WHERE username ILIKE $1", username)
            if user:
                user_id = user['telegram_id']
                
    if not user:
        await update.message.reply_text("❌ User not found in database. Send another ID/Username or /cancel.")
        return AWAITING_SEARCH
        
    panels = await db.pool.fetchval("SELECT COUNT(*) FROM panels WHERE user_telegram_id = $1", user_id)
    clones = await db.pool.fetchval("SELECT COUNT(*) FROM clone_bots WHERE owner_telegram_id = $1", user_id)
        
    status = "🔴 BANNED" if user['is_banned'] else ("⭐ VIP" if user['is_vip'] else "🟢 ACTIVE")
    
    msg = (
        f"👤 **USER PROFILE:** `{user_id}`\n\n"
        f"Status: {status}\n"
        f"Points: `{user['points']}`\n"
        f"Panels: `{panels}`\n"
        f"Clones: `{clones}`\n\n"
        f"Joined: `{user['created_at'].strftime('%Y-%m-%d %H:%M')}`\n\n"
        f"Select an action below:"
    )
    
    ban_btn = "🟢 Unban User" if user['is_banned'] else "🔴 Ban User"
    ban_action = f"admunban_{user_id}" if user['is_banned'] else f"admban_{user_id}"
    
    keyboard = [
        [InlineKeyboardButton(ban_btn, callback_data=ban_action)],
        [InlineKeyboardButton("💰 Add 500 Points", callback_data=f"admptadd_{user_id}"),
         InlineKeyboardButton("💸 Remove 500 Points", callback_data=f"admptsub_{user_id}")],
        [InlineKeyboardButton("➕ Clone Limit +1", callback_data=f"admbta_{user_id}"),
         InlineKeyboardButton("➖ Clone Limit -1", callback_data=f"admbtm_{user_id}")],
        [InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]
    ]
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

@admin_only
async def handle_user_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    try:
        user_id = int(data.split("_")[1])
    except:
        return
        
    if data.startswith("admban_"):
        await db.pool.execute("UPDATE users SET is_banned = TRUE WHERE telegram_id = $1", user_id)
        await query.edit_message_text(f"✅ User {user_id} banned.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]]))
        
    elif data.startswith("admunban_"):
        await db.pool.execute("UPDATE users SET is_banned = FALSE WHERE telegram_id = $1", user_id)
        await query.edit_message_text(f"✅ User {user_id} unbanned.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]]))
        
    elif data.startswith("admptadd_"):
        await db.pool.execute("UPDATE users SET points = points + 500 WHERE telegram_id = $1", user_id)
        current = await db.pool.fetchval("SELECT points FROM users WHERE telegram_id = $1", user_id)
        await query.edit_message_text(f"✅ Added 500 points. User now has {current} points.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]]))
        
    elif data.startswith("admptsub_"):
         await db.pool.execute("UPDATE users SET points = GREATEST(0, points - 500) WHERE telegram_id = $1", user_id)
         current = await db.pool.fetchval("SELECT points FROM users WHERE telegram_id = $1", user_id)
         await query.edit_message_text(f"✅ Removed 500 points. User now has {current} points.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]]))
         
    elif data.startswith("admbta_"):
         await db.pool.execute("UPDATE users SET force_bot_limit = COALESCE(force_bot_limit, 1) + 1 WHERE telegram_id = $1", user_id)
         await query.edit_message_text(f"✅ Incremented override max clone bot limit.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]]))
         
    elif data.startswith("admbtm_"):
         await db.pool.execute("UPDATE users SET force_bot_limit = GREATEST(0, COALESCE(force_bot_limit, 1) - 1) WHERE telegram_id = $1", user_id)
         await query.edit_message_text(f"✅ Decremented override max clone bot limit.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]]))
