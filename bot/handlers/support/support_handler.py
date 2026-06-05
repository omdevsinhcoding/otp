from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Renders standard supportive links or admin channels configured for helpdesk operations.
    """
    query = update.callback_query
    await query.answer()
    
    text = (
        f"🆘 **C2 Support & Guidance**\n\n"
        f"Having issues connecting your panels or running SMS triggers?\n"
        f"Reach out directly to the administrator handle below or check our guides.\n\n"
        f"⏰ **Support Working Hours:** `24/7 Live Coverage`"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Message Administrator", url="https://t.me/omdevsinhgohilcoding")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
