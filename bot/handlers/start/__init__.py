import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from bot.models.user_model import get_user, create_user_if_not_exists, update_user_points
from bot.models.settings_model import get_setting
from bot.models.referral_model import track_new_referral, finalize_referral_points
from bot.middlewares.ban_check import ban_check
from bot.middlewares.feature_toggle import feature_enabled
from bot.middlewares.auth_check import is_admin
from bot.services.force_join_verifier import verify_all_channels

logger = logging.getLogger(__name__)

# Global Reply Keyboard
MAIN_MENU_REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [["⬅️ Menu"]],
    resize_keyboard=True
)

@ban_check
@feature_enabled("system_enabled")
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main entry /start command handler. Registers user, processes referral parameters,
    and handles Force Join controls.
    """
    user = update.effective_user
    args = context.args
    
    # Admin bypass Force Join and registration checks if needed, but let's register them anyway
    is_adm = await is_admin(user.id)
    
    # Check if user is already registered in Neon PG
    user_record = await get_user(user.id)
    is_new = False
    
    # Extract referral code parameter: /start ref_123456789
    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].split("_")[1])
            if referred_by == user.id:  # Can't refer oneself
                referred_by = None
        except ValueError:
            pass
            
    if not user_record:
        # Register new profile
        await create_user_if_not_exists(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            referred_by=referred_by
        )
        user_record = await get_user(user.id)
        is_new = True

    # Admin bypass FJ
    if is_adm:
        await show_main_menu_message(update, context, user_record)
        return

    # Check Force Join Settings from base settings table
    fj_enabled = await get_setting("force_join_enabled", False)
    
    # If New User, handles Refer & Earn Tracking
    if is_new and referred_by:
        ref_pts = await get_setting("points_per_referral", 50)
        # Record referral relation
        await track_new_referral(referred_by, user.id, ref_pts)
        
        # If Force Join is NOT enabled, grant points immediately!
        if not fj_enabled:
            awarded, referrer, amount = await finalize_referral_points(user.id)
            if awarded:
                try:
                    await context.bot.send_message(
                        chat_id=referrer,
                        text=f"🎁 **Referral Alert!**\n\nYour friend {user.first_name} joined. You have been awarded **{amount} points**!"
                    )
                except Exception as e:
                    logger.warning(f"Could not notify referrer {referrer}: {e}")

    # If Force Join is enabled, and user hasn't completed it, show Force Join Keyboard
    if fj_enabled and not user_record.get("force_join_completed", False):
        check_result = await verify_all_channels(context.bot, user.id)
                
        if not check_result["all_joined"]:
            # Present Force Join Flow
            keyboard = []
            for ch in check_result["results"]:
                status = "✅" if ch["joined"] else "❌"
                title = ch.get("title", ch.get("username", "Channel"))
                invite_link = ch.get("invite_link")
                if not invite_link and ch.get("username"):
                    invite_link = f"https://t.me/{ch.get('username').lstrip('@')}"
                if not ch["joined"]:
                    keyboard.append([InlineKeyboardButton(f"{status} Join {title}", url=invite_link or "https://t.me")])
                else:
                    keyboard.append([InlineKeyboardButton(f"{status} {title}", callback_data="noop")])
                
            keyboard.append([InlineKeyboardButton("✅ VERIFY — I Have Joined", callback_data="verify_join")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            text = (
                f"╔═════════════════════════════════════════╗\n"
                f"║         🔒 FORCE JOIN REQUIRED        ║\n"
                f"╠═════════════════════════════════════════╣\n"
                f"║                                         ║\n"
                f"║  To activate and use this bot, you       ║\n"
                f"║  must join our official channels first.  ║\n"
                f"║                                         ║\n"
                f"║  Click the links below to join:          ║\n"
                f"╚═════════════════════════════════════════╝"
            )
            await update.message.reply_text(text, reply_markup=reply_markup)
            return

    # If user has joined, show Main Menu
    await show_main_menu_message(update, context, user_record)

async def show_main_menu_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_record: dict):
    points = user_record.get('points', 0)
    status = "VIP ⭐" if user_record.get('is_vip', False) else "Free 👤"
    user_id = update.effective_user.id
    is_adm = await is_admin(user_id)
    
    keyboard = [
        [InlineKeyboardButton("📨 Send SMS", callback_data="send_sms"), 
         InlineKeyboardButton("📥 Receive SMS", callback_data="receive_sms")],
        [InlineKeyboardButton("📋 Add Panel", callback_data="add_panel"), 
         InlineKeyboardButton("🤖 My Panels", callback_data="my_panels")],
        [InlineKeyboardButton("👥 Refer & Earn", callback_data="refer"), 
         InlineKeyboardButton("💰 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("🗄️ Data Vault (Login/Docs)", callback_data="data_vault")]
    ]
    
    is_clone = context.bot_data.get("is_clone", False)
    if not is_clone:
        if is_adm:
             keyboard.insert(3, [InlineKeyboardButton("🤖 Create Bot", callback_data="create_bot"), InlineKeyboardButton("🆘 Support", callback_data="support")])
             keyboard.append([InlineKeyboardButton("🛡️ ADMIN PANEL", callback_data="admin_menu")])
        else:
             keyboard.insert(3, [InlineKeyboardButton("🤖 Create Bot", callback_data="create_bot"), InlineKeyboardButton("🆘 Support", callback_data="support")])
    else:
        keyboard.append([InlineKeyboardButton("🆘 Support", callback_data="support")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        f"🤖 **Welcome to C2 CommandCenter Bot**\n\n"
        f"💰 **Your Points:** `{points}`\n"
        f"⭐️ **Active Tier:** `{status}`\n\n"
        f"Select a trigger component below to command devices:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        # Also send the reply keyboard to ensure it's present
        await context.bot.send_message(chat_id=user_id, text="Menu loaded.", reply_markup=MAIN_MENU_REPLY_KEYBOARD)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
        await update.message.reply_text("Static menu activated.", reply_markup=MAIN_MENU_REPLY_KEYBOARD)
