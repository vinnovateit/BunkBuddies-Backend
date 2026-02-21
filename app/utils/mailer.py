import os
from dotenv import load_dotenv
from jinja2 import Template
from typing import Dict, Any, Union, List
from pydantic import EmailStr
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
    MAIL_FROM = os.getenv("MAIL_FROM"),
    MAIL_PORT = 587,
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_FROM_NAME = "BunkBuddies",
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

fast_mail = FastMail(conf)

async def mailer(
    template_path: str, 
    email_to: Union[str, List[str]], 
    subject: str, 
    context: Dict[str, Any]
):
    
    with open(template_path, "r", encoding="utf-8") as file:
        template_content = file.read()
        
    jinja_template = Template(template_content)
    rendered_html = jinja_template.render(**context)

    if isinstance(email_to, str):
        email_to = [email_to]
        
    message = MessageSchema(
        subject=subject,
        recipients=email_to,
        body=rendered_html,
        subtype=MessageType.html
    )
    
    await fast_mail.send_message(message)