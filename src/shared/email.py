from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
from jinja2 import Template
from premailer import transform

from src.core.config import settings


def _read_template(filename: str) -> str:
    template_path = Path(__file__).parent / "templates" / filename

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as file:
        return file.read()


def _render_html(template_path: str, context: dict[str, Any]) -> str:
    raw_template = _read_template(template_path)
    rendered_html = Template(raw_template).render(**context)
    return transform(rendered_html)


class EmailService(ABC):
    @abstractmethod
    async def send_invitation(
        self,
        email: str,
        link: str,
        organization_name: str,
        is_admin: bool = False,
        administrator_name: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_token_expiry_notification(
        self,
        email: str,
        user_name: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_feedback_notification(
        self,
        email: str,
        user_name: str,
        message: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_agenda_request(
        self,
        email: str,
        calendar_event_name: str,
        calendar_event_date: str,
        calendar_event_time: str,
        calendar_event_count_attendee: str,
        calendar_event_link: str = "#",
    ) -> None:
        raise NotImplementedError


class MailjetEmailService(EmailService):
    def __init__(self) -> None:
        self.api_key = settings.MAILJET_API_KEY
        self.secret_key = settings.MAILJET_SECRET_KEY
        self.from_address = "notifications@spryplan.com"
        self.from_name = "Spry Plan"
        self.api_url = "https://api.mailjet.com/v3.1/send"

    async def send_invitation(
        self,
        email: str,
        link: str,
        organization_name: str,
        is_admin: bool = False,
        administrator_name: str | None = None,
    ) -> None:
        if is_admin:
            template = "emails/admin_invitation.html"
            subject = "🚀 You're the first admin for your organization on Spry!"
            context = {
                "invitation_link": link,
            }
        else:
            template = "emails/user_invitation.html"
            subject = "✨ You're Invited to Spry! ✨"
            context = {
                "invitation_link": link,
                "administrator_name": administrator_name or "",
                "organisation_name": organization_name,
            }

        html_content = _render_html(template, context)

        payload = {
            "Messages": [
                {
                    "From": {"Email": self.from_address, "Name": self.from_name},
                    "To": [{"Email": email, "Name": email.split("@")[0]}],
                    "Subject": subject,
                    "HTMLPart": html_content,
                    "TextPart": "",
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                auth=(self.api_key, self.secret_key),
                json=payload,
                timeout=30.0,
            )

            if response.status_code != HTTPStatus.OK:
                raise Exception(f"Email sending failed: {response.status_code} - {response.text}")

    async def send_token_expiry_notification(
        self,
        email: str,
        user_name: str | None = None,
    ) -> None:
        template = "emails/token_expiry.html"
        subject = "🔐 Google Calendar Re-authorization Required"
        context = {
            "user_name": user_name or email.split("@")[0],
            "login_link": f"{settings.frontend_domain}/login",
        }

        html_content = _render_html(template, context)

        payload = {
            "Messages": [
                {
                    "From": {"Email": self.from_address, "Name": self.from_name},
                    "To": [{"Email": email, "Name": user_name or email.split("@")[0]}],
                    "Subject": subject,
                    "HTMLPart": html_content,
                    "TextPart": "",
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                auth=(self.api_key, self.secret_key),
                json=payload,
                timeout=30.0,
            )

            if response.status_code != HTTPStatus.OK:
                raise Exception(f"Email sending failed: {response.status_code} - {response.text}")

    async def send_feedback_notification(
        self,
        email: str,
        user_name: str,
        message: str,
    ) -> None:
        template = "emails/feedback_notification.html"
        subject = "📝 New Feedback from User"
        context = {
            "email": email,
            "user_name": user_name,
            "message": message,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }

        html_content = _render_html(template, context)

        payload = {
            "Messages": [
                {
                    "From": {"Email": self.from_address, "Name": self.from_name},
                    "To": [{"Email": settings.SUPPORT_EMAIL, "Name": "Spry Support"}],
                    "Subject": subject,
                    "HTMLPart": html_content,
                    "TextPart": "",
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                auth=(self.api_key, self.secret_key),
                json=payload,
                timeout=30.0,
            )

            if response.status_code != HTTPStatus.OK:
                raise Exception(f"Email sending failed: {response.status_code} - {response.text}")

    async def send_agenda_request(
        self,
        email: str,
        calendar_event_name: str,
        calendar_event_date: str,
        calendar_event_time: str,
        calendar_event_count_attendee: str,
        calendar_event_link: str = "#",
    ) -> None:
        template = "emails/agenda_request.html"
        subject = "📄 Request of agenda for upcoming meeting"
        context = {
            "calendar_event_name": calendar_event_name,
            "calendar_event_date": calendar_event_date,
            "calendar_event_time": calendar_event_time,
            "calendar_event_count_attendee": calendar_event_count_attendee,
            "calendar_event_link": calendar_event_link,
        }

        html_content = _render_html(template, context)

        payload = {
            "Messages": [
                {
                    "From": {"Email": self.from_address, "Name": self.from_name},
                    "To": [{"Email": email, "Name": email.split("@")[0]}],
                    "Subject": subject,
                    "HTMLPart": html_content,
                    "TextPart": "",
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                auth=(self.api_key, self.secret_key),
                json=payload,
                timeout=30.0,
            )

            if response.status_code != HTTPStatus.OK:
                raise Exception(f"Email sending failed: {response.status_code} - {response.text}")


class MockEmailService(EmailService):
    async def send_invitation(
        self,
        email: str,
        link: str,
        is_admin: bool = False,
        organization_name: str | None = None,
        administrator_name: str | None = None,
    ) -> None:
        invitation_type = "admin" if is_admin else "user"
        print(f"[MOCK EMAIL] Sending {invitation_type} invitation to {email}")
        print(f"[MOCK EMAIL] Link: {link}")

        if organization_name:
            print(f"[MOCK EMAIL] Organization: {organization_name}")
        if administrator_name:
            print(f"[MOCK EMAIL] Admin: {administrator_name}")

    async def send_token_expiry_notification(
        self,
        email: str,
        user_name: str | None = None,
    ) -> None:
        print(f"[MOCK EMAIL] Token expiry notification to {email}")
        if user_name:
            print(f"[MOCK EMAIL] User: {user_name}")
        print(f"[MOCK EMAIL] Login link: {settings.frontend_domain}/login")

    async def send_feedback_notification(
        self,
        email: str,
        user_name: str,
        message: str,
    ) -> None:
        print("[MOCK EMAIL] Feedback notification to support@spryplan.com")
        print(f"[MOCK EMAIL] From: {user_name} ({email})")
        print(f"[MOCK EMAIL] Message: {message}")

    async def send_agenda_request(
        self,
        email: str,
        calendar_event_name: str,
        calendar_event_date: str,
        calendar_event_time: str,
        calendar_event_count_attendee: str,
        calendar_event_link: str = "#",
    ) -> None:
        print(f"[MOCK EMAIL] Agenda request to {email}")
        print(f"[MOCK EMAIL] Event: {calendar_event_name} on {calendar_event_date} at {calendar_event_time}")
        print(f"[MOCK EMAIL] Attendees: {calendar_event_count_attendee}")
        print(f"[MOCK EMAIL] Link: {calendar_event_link}")


def get_email_service() -> EmailService:
    if settings.MAILJET_API_KEY and settings.MAILJET_SECRET_KEY:
        return MailjetEmailService()
    return MockEmailService()
