import os
from dotenv import load_dotenv


load_dotenv()


PORTAL_BASE_URL=os.getenv("PORTAL_BASE_URL")
PORTAL_BEARER_TOKEN=os.getenv("PORTAL_BEARER_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUBMIT_API_BASE_URL = os.getenv("SUBMIT_API_BASE_URL")



if not SUBMIT_API_BASE_URL:
    raise RuntimeError("SUBMIT_API_BASE_URL is missing in .env")



if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing in .env")


if not PORTAL_BASE_URL:
    raise RuntimeError("Portal Base URL is missing in .env file")

if not PORTAL_BEARER_TOKEN:
    raise RuntimeError("Portal Baerer Token is missing in the .env file")