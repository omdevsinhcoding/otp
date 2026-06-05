import logging
from bot.models.settings_model import get_setting

logger = logging.getLogger(__name__)

async def verify_user_joined(bot, channel_id, user_id: int) -> dict:
    """
    Checks if a user is a member of the given channel/group.
    """
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return {"joined": True, "status": member.status}
        else:
            return {"joined": False, "status": member.status}
    except Exception as e:
        logger.error(f"Error checking channel {channel_id} membership: {e}")
        return {"joined": False, "status": "error"}

async def verify_all_channels(bot, user_id: int) -> dict:
    """
    Verifies all active Force Join channels.
    """
    channels = await get_setting("force_join_channels", default=[])
    if not channels:
        return {"all_joined": True, "results": []}
        
    results = []
    all_joined = True
    for channel in channels:
        check = await verify_user_joined(bot, channel["id"], user_id)
        results.append({
            **channel,
            "joined": check["joined"],
            "status": check["status"]
        })
        if not check["joined"]:
            all_joined = False
            
    return {"all_joined": all_joined, "results": results}
