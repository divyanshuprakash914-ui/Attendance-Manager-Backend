import os
from dotenv import load_dotenv
from routers import dashboard

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from auth.google_auth import router as google_auth_router
from auth.email_auth import router as email_auth_router

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(google_auth_router)
app.include_router(email_auth_router)
app.include_router(dashboard.router)


@app.get("/")
def home():
    return {
        "message": "FastAPI Backend is running."
    }


