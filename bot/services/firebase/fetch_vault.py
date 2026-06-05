import httpx
import logging

logger = logging.getLogger(__name__)

async def fetch_vault_data(firebase_url: str, branch: str) -> dict:
    """
    Fetches data from a specific branch in Firebase (e.g. login, page2, page4).
    """
    if not firebase_url or not branch:
        return {}
        
    paths_to_try = [branch, branch.capitalize(), branch.upper()]
    if branch.lower() == "login":
        paths_to_try.extend(["All_Users/Login"])
        
    async with httpx.AsyncClient(timeout=10.0) as client:
        for p in paths_to_try:
            url = f"{firebase_url.rstrip('/')}/{p}.json"
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        # Some databases nest everything under user ID
                        # If the keys look like device IDs and contain the actual data, we might need to flatten it
                        # For now, just return as is
                        return data
                    elif isinstance(data, list):
                        # Sometimes firebase arrays are returned as lists if keys are sequential
                        # Convert to dict
                        return {str(i): v for i, v in enumerate(data) if v is not None}
            except Exception as e:
                logger.error(f"Error fetching {p} from {firebase_url}: {e}")
        
    return {}
