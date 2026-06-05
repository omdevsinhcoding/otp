import logging
import asyncio
from typing import Dict
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

from bot.database import db
from bot.config import BOT_TOKEN

logger = logging.getLogger(__name__)

class CloneBotManager:
    """
    Manages the lifecycle of dynamically cloned Telegram bots.
    Stores running applications in memory and allows them to be started/stopped.
    """
    def __init__(self):
        self._running_bots: Dict[int, Application] = {} # Key: DB ID of clone
        
    async def load_and_start_all(self):
        """Called upon system startup to revive all active clones."""
        if not db.pool:
            logger.warning("Database not connected, skipping clone startup.")
            return
            
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM clone_bots WHERE is_active = TRUE")
            from bot.utils.crypto_helpers import decrypt_token
            for row in rows:
                try:
                    decrypted = decrypt_token(row['bot_token'])
                    if decrypted != BOT_TOKEN: # Safety check
                        await self.start_clone(row['id'], decrypted)
                except Exception as e:
                    logger.error(f"Error decrypting token for clone {row['id']}: {e}")

    async def start_clone(self, clone_id: int, bot_token: str):
        """Starts a specific clone bot instance."""
        if clone_id in self._running_bots:
            logger.info(f"Clone ID {clone_id} is already running.")
            return
            
        logger.info(f"Starting Clone Bot ID: {clone_id}...")
        try:
            # Build Application client
            app = Application.builder().token(bot_token).build()
            
            # Setup handlers - Import locally to avoid circle dependency
            from bot.handlers.start import start_cmd
            from bot.handlers.start.verify_join import verify_join_callback
            from bot.handlers.referral.show_referral_link import referral_menu
            from bot.handlers.wallet.show_balance import wallet_menu
            from bot.handlers.support.support_handler import support_menu
            from bot.handlers.list_panels import my_panels_menu, handle_panel_selection, handle_panel_deletion
            
            from bot.handlers.panels import add_panel_start, process_url, AWAITING_URL
            import bot.handlers.sms.send_sms as send_sms
            import bot.handlers.sms.receive_sms as receive_sms
            import bot.handlers.admin as admin
            import bot.handlers.vault as vault
            
            # The back_to_menu callback needs to be custom imported
            async def back_to_menu_callback(update, context):
                query = update.callback_query
                await query.answer()
                from bot.models.user_model import get_user
                user_record = await get_user(query.from_user.id)
                # Important: clones omit the "Create Bot" key!
                from bot.handlers.start import show_main_menu_message
                await show_main_menu_message(update, context, user_record)
            
            # Use same handlers but we need to somehow flag to 'start_cmd' that this is a clone
            # PTB allows `context.bot_data["is_clone"] = True`
            app.bot_data["is_clone"] = True
            app.bot_data["clone_id"] = clone_id
            
            app.add_handler(CommandHandler("start", start_cmd))
            app.add_handler(CommandHandler("admin", admin.admin_panel))
            app.add_handler(CallbackQueryHandler(back_to_menu_callback, pattern="^back_to_menu$"))
            app.add_handler(CallbackQueryHandler(verify_join_callback, pattern="^verify_join$"))
            
            app.add_handler(CallbackQueryHandler(referral_menu, pattern="^refer$"))
            app.add_handler(CallbackQueryHandler(wallet_menu, pattern="^wallet$"))
            app.add_handler(CallbackQueryHandler(support_menu, pattern="^support$"))
            
            app.add_handler(CallbackQueryHandler(vault.vault_menu, pattern="^data_vault$"))
            app.add_handler(CallbackQueryHandler(vault.vault_view_branch, pattern="^vault_.*$"))
            
            app.add_handler(CallbackQueryHandler(my_panels_menu, pattern="^my_panels$"))
            app.add_handler(CallbackQueryHandler(handle_panel_selection, pattern="^selpanel_\\d+$"))
            app.add_handler(CallbackQueryHandler(handle_panel_deletion, pattern="^delpanel_\\d+$"))
            
            panel_conv = ConversationHandler(
                entry_points=[CallbackQueryHandler(add_panel_start, pattern="^add_panel$")],
                states={AWAITING_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_url)]},
                fallbacks=[CommandHandler("cancel", start_cmd), CallbackQueryHandler(back_to_menu_callback, pattern="^back_to_menu$")]
            )
            app.add_handler(panel_conv)
            
            sms_send_conv = ConversationHandler(
                entry_points=[CallbackQueryHandler(send_sms.send_sms_flow_start, pattern="^send_sms$")],
                states={
                    send_sms.SELECTING_DEVICE: [CallbackQueryHandler(send_sms.device_selected_callback, pattern="^senddev_.*$")],
                    send_sms.ENTERING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_sms.phone_entered_callback)],
                    send_sms.ENTERING_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_sms.message_entered_callback)],
                    send_sms.SELECTING_SIM: [CallbackQueryHandler(send_sms.sim_selected_callback, pattern="^sendsim_.*$")]
                },
                fallbacks=[CallbackQueryHandler(send_sms.cancel_sms_flow, pattern="^cancel_sms$"), CommandHandler("cancel", start_cmd)]
            )
            app.add_handler(sms_send_conv)
            
            sms_receive_conv = ConversationHandler(
                entry_points=[CallbackQueryHandler(receive_sms.start_receive_sms_flow, pattern="^receive_sms$")],
                states={
                    receive_sms.CHOOSING_RECV_DEVICE: [CallbackQueryHandler(receive_sms.view_intercepted_sms, pattern="^recvdev_.*$")]
                },
                fallbacks=[CallbackQueryHandler(send_sms.cancel_sms_flow, pattern="^cancel_sms$"), CommandHandler("cancel", start_cmd)]
            )
            app.add_handler(sms_receive_conv)
            
            # NOTE: We DO NOT add create_bot handlers for clones
            
            app.add_handler(CallbackQueryHandler(admin.admin_panel, pattern="^admin_menu$"))
            app.add_handler(CallbackQueryHandler(admin.analytics_view, pattern="^adm_analytics$"))
            app.add_handler(CallbackQueryHandler(admin.admin_kill_switch_menu, pattern="^adm_killswitch$"))
            app.add_handler(CallbackQueryHandler(admin.handle_killswitch_toggle, pattern="^killsys_.*$"))
            
            broadcast_conv = ConversationHandler(
                entry_points=[CallbackQueryHandler(admin.broadcast_start, pattern="^adm_broadcast$")],
                states={admin.AWAITING_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin.broadcast_processing)]},
                fallbacks=[CommandHandler("cancel", start_cmd)]
            )
            app.add_handler(broadcast_conv)
            
            # Initialize and start polling
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            
            self._running_bots[clone_id] = app
            logger.info(f"✅ Clone ID {clone_id} started successfully.")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Clone ID {clone_id}: {e}")

    async def stop_clone(self, clone_id: int):
        """Gracefully stops a running clone bot."""
        if clone_id in self._running_bots:
            try:
                app = self._running_bots[clone_id]
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
                del self._running_bots[clone_id]
                logger.info(f"⏹️ Clone ID {clone_id} stopped.")
            except Exception as e:
                logger.error(f"Error stopping Clone ID {clone_id}: {e}")

    async def expiration_monitor(self):
        """Periodically checks for expired VIP clones and shuts them down."""
        while True:
            await asyncio.sleep(3600) # Check every 1 hour
            if not db.pool:
                continue
            try:
                async with db.pool.acquire() as conn:
                    # Find running expired clones
                    rows = await conn.fetch("SELECT id FROM clone_bots WHERE is_active = TRUE AND expires_at < NOW()")
                    for row in rows:
                        clone_id = row['id']
                        await conn.execute("UPDATE clone_bots SET is_active = FALSE WHERE id = $1", clone_id)
                        await self.stop_clone(clone_id)
            except Exception as e:
                logger.error(f"Error in expiration_monitor: {e}")

# Global instance
clone_manager = CloneBotManager()
