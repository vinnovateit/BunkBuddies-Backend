import os
from pathlib import Path
from typing import Any, Dict, List, Union

from dotenv import load_dotenv
from fastapi_mail import (
    ConnectionConfig,
    FastMail,
    MessageSchema,
    MessageType,
    MultipartSubtypeEnum,
)
from jinja2 import Template

project_root = Path(__file__).resolve().parents[2]
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

email_template_dir = Path(__file__).resolve().parents[1] / "templates" / "emails"

BB_LOGO_CID = "bb_logo"
VINN_LOGO_CID = "vinn_logo"
MAX_RECIPIENTS_PER_BATCH = 100


def _inline_logo_attachment(
    file_name: str,
    cid: str,
    mime_type: str,
    mime_subtype: str,
) -> Dict[str, Any] | None:
    asset_path = email_template_dir / file_name
    if not asset_path.exists():
        return None
    return {
        "file": str(asset_path),
        "mime_type": mime_type,
        "mime_subtype": mime_subtype,
        "headers": {
            "Content-ID": f"<{cid}>",
            "Content-Disposition": f'inline; filename="{asset_path.name}"',
        },
    }


def _build_inline_logo_attachments() -> List[Dict[str, Any]]:
    attachments: List[Dict[str, Any]] = []
    bb_logo = _inline_logo_attachment("bb_logo.png", BB_LOGO_CID, "image", "png")
    vinn_logo = _inline_logo_attachment("Vinn.png", VINN_LOGO_CID, "image", "png")
    if bb_logo:
        attachments.append(bb_logo)
    if vinn_logo:
        attachments.append(vinn_logo)
    return attachments


def _chunk_recipients(recipients: List[str], batch_size: int = MAX_RECIPIENTS_PER_BATCH) -> List[List[str]]:
    size = max(batch_size, 1)
    return [recipients[i : i + size] for i in range(0, len(recipients), size)]


conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_FROM_NAME="BunkBuddies",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)

fast_mail = FastMail(conf)


async def mailer(
    template_path: str,
    email_to: Union[str, List[str]],
    subject: str,
    context: Dict[str, Any],
):

    with open(template_path, "r", encoding="utf-8") as file:
        template_content = file.read()

    jinja_template = Template(template_content)
    rendered_html = jinja_template.render(
        bb_logo_src=f"cid:{BB_LOGO_CID}",
        vinn_logo_src=f"cid:{VINN_LOGO_CID}",
        **context,
    )

    if isinstance(email_to, str):
        recipients = [email_to.strip()] if email_to.strip() else []
    else:
        recipients = [email.strip() for email in email_to if isinstance(email, str) and email.strip()]

    if not recipients:
        return

    attachments = _build_inline_logo_attachments()
    for recipient_batch in _chunk_recipients(recipients):
        message = MessageSchema(
            subject=subject,
            recipients=recipient_batch,
            body=rendered_html,
            subtype=MessageType.html,
            multipart_subtype=MultipartSubtypeEnum.related,
            attachments=attachments,
        )
        await fast_mail.send_message(message)
