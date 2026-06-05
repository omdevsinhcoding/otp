from bot.middlewares.auth_check import admin_only

# Duplicated fallback path to avoid import file missing on template codes
__all__ = ["admin_only"]
