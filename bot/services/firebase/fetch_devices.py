import httpx
import logging

logger = logging.getLogger(__name__)

async def fetch_all_devices(firebase_url: str) -> dict:
    """
    Fetches all registered devices from multiple known nodes.
    Returns a dictionary of parsed devices mapped by device ID.
    """
    if not firebase_url:
        return {}
        
    paths = ["user_data", "Info", "user_list", "All_User", "All_Users"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        for path in paths:
            url = f"{firebase_url.rstrip('/')}/{path}.json"
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        # Normalize device fields
                        normalized = {}
                        for dev_id, info in data.items():
                            if isinstance(info, dict):
                                brand = info.get("d_name") or info.get("Name") or info.get("name") or "Generic Device"
                                battery = str(info.get("battery", info.get("Battery", "N/A")))
                                status = str(info.get("status", "unknown")).lower()
                                normalized[dev_id] = {
                                    "brand": brand,
                                    "battery": battery,
                                    "status": status,
                                    "node_path": path,
                                    "raw": info
                                }
                        return normalized
            except Exception as e:
                logger.error(f"Error fetching from {url}: {e}")
                
    return {}
