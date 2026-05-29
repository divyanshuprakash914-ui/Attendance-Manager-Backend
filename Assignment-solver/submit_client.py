import os
import httpx
from dotenv import load_dotenv

load_dotenv()


class SubmitClient:
    def __init__(self):
        self.base_url = os.getenv("SUBMIT_API_BASE_URL")
        self.token = os.getenv("PORTAL_BEARER_TOKEN")

    async def patch(self, endpoint: str, payload: dict):
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.patch(
                url,
                json=payload,
                headers=headers,
            )

        try:
            data = response.json()
        except Exception:
            data = response.text

        return {
            "success": response.status_code in [200, 201],
            "status_code": response.status_code,
            "data": data,
        }