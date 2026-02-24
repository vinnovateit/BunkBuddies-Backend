from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import httpx
from jinja2 import Template

from config import settings

BB_LOGO_CID = "bb_logo"
VINN_LOGO_CID = "vinn_logo"


def _resolve_template_path(template_path: str) -> Path:
    path = Path(template_path)
    if path.is_absolute():
        return path
    project_root = Path(__file__).resolve().parents[2]
    return project_root / path


def _template_assets_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "emails"


def _normalize_recipients(email_to: Union[str, List[str]]) -> List[str]:
    if isinstance(email_to, str):
        email = email_to.strip()
        return [email] if email else []
    return [email.strip() for email in email_to if isinstance(email, str) and email.strip()]


def _build_inline_attachments() -> Tuple[List[Dict[str, Any]], str | None, str | None]:
    attachments: List[Dict[str, Any]] = []
    bb_logo_src: str | None = None
    vinn_logo_src: str | None = None

    assets_dir = _template_assets_dir()
    bb_logo_path = assets_dir / "bb_logo.png"
    if bb_logo_path.exists():
        attachments.append(
            {
                "filename": bb_logo_path.name,
                "content": base64.b64encode(bb_logo_path.read_bytes()).decode("ascii"),
                "encoding": "base64",
                "contentType": "image/png",
                "cid": BB_LOGO_CID,
                "contentDisposition": "inline",
            }
        )
        bb_logo_src = f"cid:{BB_LOGO_CID}"

    vinn_logo_path = assets_dir / "logo.png"
    if not vinn_logo_path.exists():
        vinn_logo_path = assets_dir / "Vinn.png"
    if vinn_logo_path.exists():
        attachments.append(
            {
                "filename": vinn_logo_path.name,
                "content": base64.b64encode(vinn_logo_path.read_bytes()).decode("ascii"),
                "encoding": "base64",
                "contentType": "image/png",
                "cid": VINN_LOGO_CID,
                "contentDisposition": "inline",
            }
        )
        vinn_logo_src = f"cid:{VINN_LOGO_CID}"

    return attachments, bb_logo_src, vinn_logo_src


def _render_html(template_path: str, context: Dict[str, Any], *, bb_logo_src: str | None, vinn_logo_src: str | None) -> str:
    template_file = _resolve_template_path(template_path)
    with template_file.open("r", encoding="utf-8") as file:
        template_content = file.read()

    template = Template(template_content)
    return template.render(
        bb_logo_src=bb_logo_src,
        vinn_logo_src=vinn_logo_src,
        **context,
    )


async def send_via_nodemailer(
    template_path: str,
    email_to: Union[str, List[str]],
    subject: str,
    context: Dict[str, Any],
) -> None:
    recipients = _normalize_recipients(email_to)
    if not recipients:
        return

    api_url = settings.nodemailer_api_url.strip()
    if not api_url:
        raise RuntimeError("NODEMAILER_API_URL is not configured")

    attachments, bb_logo_src, vinn_logo_src = _build_inline_attachments()
    rendered_html = _render_html(
        template_path,
        context,
        bb_logo_src=bb_logo_src,
        vinn_logo_src=vinn_logo_src,
    )
    timeout = httpx.Timeout(max(settings.nodemailer_timeout_seconds, 5))

    async with httpx.AsyncClient(timeout=timeout) as client:
        for recipient in recipients:
            response = await client.post(
                api_url,
                json={
                    "to": recipient,
                    "subject": subject,
                    "html": rendered_html,
                    "attachments": attachments,
                },
            )
            if response.status_code >= 400:
                response_text = (response.text or "").strip()
                raise RuntimeError(
                    f"Nodemailer API error ({response.status_code}) for {recipient}: {response_text[:300]}"
                )
