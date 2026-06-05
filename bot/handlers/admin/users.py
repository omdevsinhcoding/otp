import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.middlewares.auth_check import admin_only
from bot.database import db

logger = logging.getLogger(__name__)

@admin_only
async def users_list_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # We will do a generic user count and a search button
    
    if not db.pool:
         return
         
    async with db.pool.acquire() as conn:
        tot_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        banned = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned = TRUE")
        
    text = (
        f"👥 **User Management**\n\n"
        f"Total Users: `{tot_users}`\n"
        f"Banned: `{banned}`\n"
        f"Active: `{tot_users - banned}`\n\n"
        "Click below to search for a user or manage bans."
    )
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search User by ID", callback_data="adm_search_user")],
        [InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
