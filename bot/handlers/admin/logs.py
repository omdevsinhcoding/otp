import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from bot.middlewares.auth_check import admin_only

logger = logging.getLogger(__name__)

@admin_only
async def logs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Parse potential filter
    cat_filter = None
    if query.data.startswith("admlog_"):
        cat_filter = query.data.split("_")[1]
        if cat_filter == "all":
            cat_filter = None
            
    from bot.database import db
    import json
    logs_text = "📝 **System Logs (Last 20)**\n\n"
    
    if db.pool:
        async with db.pool.acquire() as conn:
            if cat_filter:
                rows = await conn.fetch("SELECT * FROM system_logs WHERE category = $1 ORDER BY created_at DESC LIMIT 20", cat_filter)
            else:
                rows = await conn.fetch("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 20")
                
            for r in rows:
                dt = r['created_at'].strftime("%m-%d %H:%M")
                tgt = f" [Uid: {r['target_user']}]" if r['target_user'] else ""
                logs_text += f"`{dt}` **[{r['category']}]** {r['action']}{tgt}\n"
    
    if len(logs_text) < 50:
        logs_text += "No logs found."
        
    keyboard = [
        [
            InlineKeyboardButton("All", callback_data="admlog_all"),
            InlineKeyboardButton("Users", callback_data="admlog_user"),
            InlineKeyboardButton("Admin", callback_data="admlog_admin")
        ],
        [
            InlineKeyboardButton("SMS", callback_data="admlog_sms"),
            InlineKeyboardButton("Panels", callback_data="admlog_panel"),
            InlineKeyboardButton("Sec.", callback_data="admlog_security")
        ],
        [InlineKeyboardButton("📥 Export Users DB", callback_data="export_users")],
        [InlineKeyboardButton("⬅️ Back Menu", callback_data="admin_menu")]
    ]
    await query.edit_message_text(logs_text, reply_markup=InlineKeyboardMarkup(keyboard))

@admin_only
async def handle_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data != "export_users":
        return
        
    await query.edit_message_text("🔄 Generating CSV backup...")
    
    import csv
    import io
    from bot.database import db
    
    f = io.StringIO()
    writer = csv.writer(f)
    writer.writerow(["id", "telegram_id", "username", "points", "is_vip", "panels_count", "clone_bots_count", "created_at"])
    
    if db.pool:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, telegram_id, username, points, is_vip, panels_count, clone_bots_count, created_at FROM users")
            for r in rows:
                writer.writerow([r['id'], r['telegram_id'], r['username'], r['points'], r['is_vip'], r['panels_count'], r['clone_bots_count'], r['created_at']])
                
    f.seek(0)
    
    v = f.getvalue().encode('utf-8')
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=v,
        filename="users_backup.csv",
        caption="✅ User Database Backup"
    )
    await logs_menu(update, context)
