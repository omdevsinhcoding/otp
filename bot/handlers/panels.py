import httpx
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from bot.models.user_model import update_user_points
from bot.models.panel_model import add_panel, get_user_panels
from bot.models.settings_model import get_setting
from bot.services.firebase_service import analyze_firebase_url
from bot.middlewares.feature_toggle import feature_enabled
from bot.middlewares.ban_check import ban_check

logger = logging.getLogger(__name__)

AWAITING_URL = 1

@ban_check
@feature_enabled("f_add_panel")
async def add_panel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Kicks off panel registration flow. Validates limits from Neon PostgreSQL.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Check if user has enough points
    from bot.models.user_model import get_user
    user_record = await get_user(user_id)
    cost = await get_setting("cost_add_panel", 20)
    
    # If not VIP, check points
    if not user_record.get('is_vip') and user_record.get('points', 0) < cost:
        await query.edit_message_text(
            f"🚫 **Insufficient Points!**\n\nYou need **{cost} points** to add a new panel.\n"
            f"Current balance: `{user_record.get('points', 0)} points`\n\n"
            f"Share your referral link to earn more points!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]])
        )
        return ConversationHandler.END

    panels = await get_user_panels(user_id)
    panel_limit = await get_setting("max_panels_per_user", 5)
    
    if len(panels) >= panel_limit:
        await query.edit_message_text(
            f"🚫 **Limit Reached!**\n\nYou have already registered **{len(panels)}/{panel_limit} panels**.\n"
            f"Delete one from 'My Panels' before adding more.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="back_to_menu")]])
        )
        return ConversationHandler.END
        
    await query.edit_message_text(
        "📋 **Add Realtime Database**\n\n"
        "Please paste your Firebase RTDB URL (e.g. `https://my-project-default-rtdb.firebaseio.com/`):\n\n"
        "💡 _Tip: You can also just paste the database name (like 'pmsjdj-default-rtdb') and our auto-builder will format it!_\n\n"
        "Type /cancel to abort."
    )
    return AWAITING_URL

async def process_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processes and validates the input URL or token string using Section 1 rules.
    """
    user_id = update.effective_user.id
    raw_input = update.message.text.strip()
    
    # Check for cancel command
    if raw_input.lower() == "/cancel":
        await update.message.reply_text("❌ Action cancelled.")
        return ConversationHandler.END

    # Partial/Raw URL autocompletion (Scenario #11)
    url = raw_input
    if "firebaseio.com" not in url and ".firebasestorage.app" not in url:
        # Check if they pasted just a project sub-domain token
        autocompleted = f"https://{url.rstrip('/')}.firebaseio.com/.json"
        # Confirm autocompletion suggestion with user
        await update.message.reply_text(
            f"🔄 Autodetected abbreviated handle: Autocompleting raw token to:\n`{autocompleted}`"
        )
        url = autocompleted
        
    # Standard format validation
    target_url = url if url.endswith(".json") else f"{url.rstrip('/')}/.json"

    # Block storage bucket endpoints (Scenario #7)
    if ".firebasestorage.app" in raw_input or ".firebasestorage.app" in target_url:
        await update.message.reply_text(
            "❌ **Error:** Ye Firebase **Storage Bucket** hai, Realtime Database (RTDB) nahi.\n"
            "RTDB URLs should terminate with `.firebaseio.com/`"
        )
        return ConversationHandler.END

    msg = await update.message.reply_text("🔍 Connecting and analyzing Firebase DB schema...")
    
    # Check deduplication (Scenario #10)
    user_panels = await get_user_panels(user_id)
    for p in user_panels:
        cleaned_existing = p['firebase_url'].rstrip('/').replace('/.json', '')
        cleaned_new = url.rstrip('/').replace('/.json', '')
        if cleaned_existing == cleaned_new:
            await msg.edit_text("⚠️ **Error:** Ye Firebase URL pehle se added hai. Duplicate panels can't be added.")
            return ConversationHandler.END

    # Run Analysis Engine
    result = await analyze_firebase_url(url)
    
    if result["status"] == "error":
        # Classification alerts parsed cleanly (Scenarios #3, #4, #5, #6, #8, #9, #12, #13)
        await msg.edit_text(f"❌ **Validation Failed!**\n\nReason: {result['message']}")
        return ConversationHandler.END
        
    elif result["status"] == "warning":
        # Blank / Empty Database prompt (Scenario #2)
        # Store temporary url in context state and let them add anyway
        context.user_data["pending_panel_url"] = url
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Add It", callback_data="confirm_add_empty"),
             InlineKeyboardButton("❌ No, Cancel", callback_data="back_to_menu")]
        ]
        await msg.edit_text(
            "⚠️ **Empty Database Alert!**\n\nHTTP GET 200 returned a `null` response. This database is online but completely empty.\n"
            "Would you like to add it anyway?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
        
    elif result["status"] == "success":
        # Successfully fetched structure! (Scenario #1)
        patterns = result.get("patterns", {})
        data_summary = (
            f"✅ **Database Verified & Connected Successfully!**\n\n"
            f"📋 **Detected Nodes Map:**\n"
            f" • User Accounts: `{'Detected 🟢' if patterns.get('has_user_data') else 'Absent 🔴'}`\n"
            f" • Intercepted SMS: `{'Detected 🟢' if patterns.get('has_sms') else 'Absent 🔴'}`\n"
            f" • Phished Logins: `{'Detected 🟢' if patterns.get('has_login') else 'Absent 🔴'}`\n\n"
            f"Adding panel to your control dock..."
        )
        await msg.edit_text(data_summary)
        
        # Deduct standard points for Add Panel feature before executing
        cost = await get_setting("cost_add_panel", 20)
        from bot.models.user_model import get_user
        user_record = await get_user(user_id)
        
        is_vip = user_record.get('is_vip', False) if user_record else False
        if not is_vip:
            new_bal = await update_user_points(user_id, -cost)
            if new_bal is None:
                await update.message.reply_text(f"🚫 **Insufficient Points!** You need {cost} points to add a panel.")
                return ConversationHandler.END
        
        # Insert records inside Neon DB
        added = await add_panel(user_id, url)
        if added:
            if not is_vip:
                await update.message.reply_text(f"💳 Standard fee of **{cost} pts** deducted successfully from wallet.")
            
            # Notify admins
            from bot.config import ADMINS
            if ADMINS:
                from telegram import Bot
                from bot.config import BOT_TOKEN
                try:
                    admin_bot = Bot(BOT_TOKEN)
                    msg_text = f"🔔 **New Panel Added!**\n\n👤 User ID: `{user_id}`\n📋 URL: `{url}`"
                    for adm_id in ADMINS:
                        await admin_bot.send_message(chat_id=adm_id, text=msg_text)
                except Exception as e:
                    logger.error(f"Failed to notify admins of new panel: {e}")
        else:
            # Revert points if db fail
            if not is_vip:
                await update_user_points(user_id, cost)
            await update.message.reply_text("Failed to register database inside system.")
            
        return ConversationHandler.END
