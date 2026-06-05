import httpx
import logging

logger = logging.getLogger(__name__)

async def fetch_device_sms(firebase_url: str, device_id: str) -> dict:
    """
    Fetches intercepted message logs from multiple common nodes on Firebase RTDB.
    """
    if not firebase_url or not device_id:
        return {}
        
    paths = ["user_sms", "Sms", "sms", "messages"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        for path in paths:
            url = f"{firebase_url.rstrip('/')}/{path}/{device_id}.json"
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.error(f"Error fetching from {url}: {e}")
                
    return {}
