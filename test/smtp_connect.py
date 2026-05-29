import os
import smtplib
from dotenv import load_dotenv

load_dotenv()

print("HOST:", repr(os.getenv("EMAIL_HOST")))
print("PORT:", repr(os.getenv("EMAIL_PORT")))
print("USERNAME:", repr(os.getenv("EMAIL_USERNAME")))

try:
    with smtplib.SMTP(
        os.getenv("EMAIL_HOST"),
        int(os.getenv("EMAIL_PORT")),
        timeout=20,
    ) as server:
        server.set_debuglevel(1)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(
            os.getenv("EMAIL_USERNAME"),
            os.getenv("EMAIL_PASSWORD")
        )

        print("SMTP worked successfully")


except Exception as e:
    print("SMTP error :", repr(e))



