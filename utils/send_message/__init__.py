import os
import requests
from jinja2 import Template
from premailer import transform


def read_template(filename: str) -> str:
    template_path = os.path.join("utils", "send_message", "templates", filename)
    with open(template_path, "r", encoding="utf-8") as file:
        return file.read()


def render_template(template_str: str, context: dict) -> str:
    template = Template(template_str)
    return template.render(**context)


def inline_styles(html: str) -> str:
    return transform(html)


def send_email(to_address: str,
               subject: str,
               html_content: str,
               from_address: str = "hello@spryplan.com",
               reply_tos: list = None):
    try:
        inlined_html = inline_styles(html_content)
        payload = {
            "Messages": [
                {
                    "From": {
                        "Email": from_address,
                        "Name": from_address.split("@")[0]
                    },
                    "To": [
                        {
                            "Email": to_address,
                            "Name": to_address.split("@")[0]
                        }
                    ],
                    "Subject": subject,
                    "HTMLPart": inlined_html,
                    "TextPart": ""  # Optional plain text version
                }
            ]
        }

        if reply_tos:
            payload["Messages"][0]["ReplyTo"] = {
                "Email": reply_tos[0],
                "Name": reply_tos[0].split("@")[0]
            }

        response = requests.post(
            "https://api.mailjet.com/v3.1/send",
            auth=(os.getenv("MAILJET_API_KEY"), os.getenv("MAILJET_SECRET_KEY")),
            json=payload
        )

        if response.status_code == 200:
            message_id = response.json()['Messages'][0]['To'][0]['MessageUUID']
            return message_id
        else:
            raise Exception("Email sending failed")
    except Exception as e:
        raise e


def send_user_invitation(email: str, administrator_name: str = '', organisation_name: str = ''):
    raw_template = read_template("emails/user_invitation.html")
    html_content = render_template(raw_template, {
        "administrator_name": administrator_name,
        "organisation_name": organisation_name
    })

    send_email(
        to_address=email,
        subject="✨ You’re Invited to Spry! ✨",
        html_content=html_content
    )


def send_agenda_request(email: str,
                        calendar_event_name: str = "",
                        calendar_event_date: str = "",
                        calendar_event_time: str = "",
                        calendar_event_count_attendee: str = "",
                        calendar_event_link: str = "#"):
    raw_template = read_template("emails/agenda_request.html")
    html_content = render_template(raw_template, {
        "calendar_event_name": calendar_event_name,
        "calendar_event_date": calendar_event_date,
        "calendar_event_time": calendar_event_time,
        "calendar_event_count_attendee": calendar_event_count_attendee,
        "calendar_event_link": calendar_event_link
    })
    send_email(
        to_address=email,
        subject="📄 Request of agenda for upcoming meeting",
        html_content=html_content
    )


def send_admin_invitation(email: str):
    raw_template = read_template("emails/admin_invitation.html")
    html_content = render_template(raw_template, {})
    send_email(
        to_address=email,
        subject="🚀 You’re the first admin for your organization on Spry!",
        html_content=html_content
    )
