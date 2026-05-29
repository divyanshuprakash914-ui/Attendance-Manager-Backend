import os
import smtplib
import socket
from email.message import EmailMessage


from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature



router = APIRouter(
    prefix="/auth/email",
    tags=["EmailAuth"],
)

class EmailLoginRequest(BaseModel):
    email:EmailStr


def get_serial():
    return URLSafeTimedSerializer(os.getenv("MAGIC_LINK_SECRET"))


def send_magic_link_email(to_email: str, magic_link: str):
    msg=EmailMessage()
    msg["Subject"] = "Login to Attendence Manager"
    msg["From"] = os.getenv("EMAIL_USERNAME")
    msg["To"] = to_email

    msg.set_content(
        f"""
        Hi,
        Click this link to login :
        {magic_link}
        This link will expire in 10 minutes.

        If you did't request it just ignore the mail.

        Thanks...

    """
    )

    try:
        with smtplib.SMTP(
            os.getenv("EMAIL_HOST"),
            int(os.getenv("EMAIL_PORT")),
            timeout=30,
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(
                os.getenv("EMAIL_USERNAME"),
                os.getenv("EMAIL_PASSWORD")
            )
            server.send_message(msg)
            
    except (socket.gaierror, TimeoutError, OSError) as e:
        raise HTTPException(
            status_code=503,
            detail=f"Email server is unreachable. Check your internet/network or SMTP settings. Error: {e}",
        )

    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            status_code=401,
            detail="Gmail login failed. Use a valid Gmail App Password, not your normal Gmail password.",
        )

    except smtplib.SMTPException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email: {e}",
        )


@router.post("/request-link")
def request_magic_link(data: EmailLoginRequest):
    serializer=get_serial()

    token=serializer.dumps(data.email, salt="email-login")

    magic_link = f"{os.getenv('BACKEND_URL')}/auth/email/verify?token={token}"
    send_magic_link_email(data.email, magic_link)

    return {
        "message" : "Login link sent to your email"
    }



@router.get("/verify")
def verify_magic_link(request:Request, token:str):
    serializer = get_serial()

    try:
        email=serializer.loads(
            token,
            salt="email-login",
            
            max_age=600,
        )

    except SignatureExpired:
        raise HTTPException(
            status_code=400,
            detail='Login Link Expired'
        )
    
    except BadSignature:
        raise HTTPException(
            status_code=400,
            detail="Invalid Login Link",
        )
    

    request.session["user"] = {
        "email" : email,
        "name" : email.split("@")[0],
        "picture" : None,
        "login_type" : "email",
    }


    return RedirectResponse(url=f"{os.getenv('FRONTEND_URL')}/dashboard")



