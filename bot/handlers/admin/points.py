import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.middlewares.auth_check import admin_only
from bot.database import db

logger = logging.getLogger(__name__)

@admin_only
async def points_mgmt_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not db.pool:
         return
         
    async with db.pool.acquire() as conn:
        tot_pts = await conn.fetchval("SELECT SUM(points) FROM users")
        top_users = await conn.fetch("SELECT telegram_id, points FROM users ORDER BY points DESC LIMIT 5")
        
    text = (
         f"💰 **Points Economy**\n\n"
         f"Total points in circulation: `{tot_pts}`\n\n"
         "**Top 5 Holders:**\n"
    )
    
    for u in top_users:
         text += f" • UID `{u['telegram_id']}` : `{u['points']}` pts\n"
         
    text += "\nTo manually add/remove points from users, go to **Users Management -> Search User ID**."
    
    keyboard = [[InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
