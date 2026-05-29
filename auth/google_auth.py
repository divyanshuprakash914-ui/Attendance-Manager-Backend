import os
from dotenv import load_dotenv

from fastapi import APIRouter, Request
from authlib.integrations.starlette_client import OAuth
from fastapi.responses import RedirectResponse, JSONResponse

load_dotenv()

router = APIRouter(
    prefix="/auth",
    tags=["Google Auth"]
)

oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    },
)


@router.get("/google/login")
async def google_login(request: Request):
    redirect_url = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_url)


@router.get("/google/callback")
async def google_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")

    if not user_info:
        user_info = await oauth.google.userinfo(token=token)

    request.session["user"] = {
        "email": user_info["email"],
        "name": user_info["name"],
        "picture": user_info.get("picture"),
    }

    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/dashboard")


@router.get("/me")
def auth_me(request: Request):
    user = request.session.get("user")

    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "message": "Not logged in"
            }
        )

    return user


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return {
        "message": "Logged Out Successfully"
    }