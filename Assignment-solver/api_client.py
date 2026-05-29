import httpx
from config import PORTAL_BASE_URL, PORTAL_BEARER_TOKEN

class PortalAPIClient:
    def __init__(self):
        self.base_url=PORTAL_BASE_URL.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {PORTAL_BEARER_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }


    async def get(self, endpoint:str):
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=self.headers)

        if response.status_code >= 400:
            return {
                "success" : False,
                "status_code" : response.status_code,
                "error" : response.text,
            }
        
        try:
            data = response.json()
        except ValueError:
            data = response.text

        return {
            "success": True,
            "status_code": response.status_code,
            "data": data,
        }
    

    async def post(self, endpoint: str, payload: dict):
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=payload,
            )

        if response.status_code >= 400:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
            }

        try:
            data = response.json()
        except ValueError:
            data = response.text

        return {
            "success": True,
            "status_code": response.status_code,
            "data": data,
        }