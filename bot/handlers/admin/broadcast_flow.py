import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from bot.middlewares.auth_check import admin_only
from bot.database import db

logger = logging.getLogger(__name__)

(AWAIT_MSG,
 AWAIT_Q_BTN, 
 AWAIT_BTN_TEXT, 
 AWAIT_BTN_URL,
 AWAIT_PREVIEW_CONFIRM) = range(5)

@admin_only
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Reset context
    context.user_data['broadcast_msg'] = ""
    context.user_data['broadcast_btns'] = []
    
    await query.edit_message_text(
        "📢 **System-wide Broadcaster Node**\n\n"
        "Send the message that you want to broadcast to all users (HTML/Markdown supported).\n\n"
        "Type /cancel to abort broadcast."
    )
    return AWAIT_MSG

@admin_only
async def receive_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "/cancel":
        await update.message.reply_text("Broadcast canceled.")
        return ConversationHandler.END
        
    context.user_data['broadcast_msg'] = text
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes", callback_data="bcbtn_yes"), InlineKeyboardButton("❌ No", callback_data="bcbtn_no")]
    ]
    await update.message.reply_text("Do you want to add inline buttons?", reply_markup=InlineKeyboardMarkup(keyboard))
    return AWAIT_Q_BTN

@admin_only
async def q_btn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "bcbtn_yes":
        await query.edit_message_text("Send the **text** for the button (or /cancel):")
        return AWAIT_BTN_TEXT
    else:
        # Move to preview
        return await show_preview(update, context)
        
@admin_only
async def receive_btn_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "/cancel":
        await update.message.reply_text("Broadcast canceled.")
        return ConversationHandler.END
        
    context.user_data['temp_btn_text'] = text
    await update.message.reply_text("Great! Now send the **URL** for this button:")
    return AWAIT_BTN_URL

@admin_only
async def receive_btn_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if url == "/cancel":
        await update.message.reply_text("Broadcast canceled.")
        return ConversationHandler.END
        
    # Validation
    if not url.startswith("http"):
        await update.message.reply_text("URL must start with http or https. Send again.")
        return AWAIT_BTN_URL
        
    text = context.user_data['temp_btn_text']
    context.user_data['broadcast_btns'].append([InlineKeyboardButton(text, url=url)])
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Another Row", callback_data="bcbtn_yes")],
        [InlineKeyboardButton("➡️ Preview & Send", callback_data="bcbtn_no")]
    ]
    await update.message.reply_text("Button added! Want to add another?", reply_markup=InlineKeyboardMarkup(keyboard))
    return AWAIT_Q_BTN

async def show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = context.user_data.get('broadcast_msg', '')
    btns = context.user_data.get('broadcast_btns', [])
    
    reply_markup = InlineKeyboardMarkup(btns) if btns else None
    
    keyboard = [
        [InlineKeyboardButton("✅ Send to All", callback_data="bc_send"), InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel")]
    ]
    
    try:
        reply = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"**Preview:**\n\n{msg_text}",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        await reply.reply_text("Proceed with sending?", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Preview error: {e}\nPlease try again.")
        return ConversationHandler.END
        
    return AWAIT_PREVIEW_CONFIRM

@admin_only
async def send_broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "bc_cancel":
        await query.edit_message_text("Broadcast canceled.")
        return ConversationHandler.END
        
    msg_text = context.user_data.get('broadcast_msg', '')
    btns = context.user_data.get('broadcast_btns', [])
    reply_markup = InlineKeyboardMarkup(btns) if btns else None
    
    await query.edit_message_text("🚀 Sending broadcast...")
    
    users = []
    if db.pool:
        async with db.pool.acquire() as conn:
             rows = await conn.fetch("SELECT telegram_id FROM users")
             users = [r['telegram_id'] for r in rows]
             
    success = 0
    failed = 0
    
    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=msg_text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            success += 1
        except Exception:
            failed += 1
            
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"✅ **Broadcast Completed!**\n\n"
        f" • Successful Delivery: `{success}/{len(users)}`\n"
        f" • Rejected/Blocked: `{failed}`"
    )
    return ConversationHandler.END
