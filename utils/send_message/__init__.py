import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def read_template(filename: str) -> str:
    template_path = os.path.join("utils", "send_message", "templates", filename)
    with open(template_path, "r", encoding="utf-8") as file:
        return file.read()


def send_email(to_email: str, subject: str, html_content: str, from_email: str = 'hello@spryplan.com'):
    try:
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        sg.send(message)
    except Exception as e:
        print("Send Email (SendGridAPIClient):", e)


def send_user_invitation(email: str):
    html_content = read_template("emails/user_invitation.html")
    send_email(
        to_email=email,
        subject="✨ You’re Invited to Spry! ✨",
        html_content=html_content
    )


def send_agenda_request(email: str, calendar_event_link: str = "#"):
    raw_template = read_template("emails/agenda_request.html")
    html_content = raw_template.format(calendar_event_link=calendar_event_link)
    send_email(
        to_email=email,
        subject="🎯 Agenda Request for Your Upcoming Meeting",
        html_content=html_content
    )


def send_admin_invitation(email: str):
    html_content = read_template("emails/admin_invitation.html")
    send_email(
        to_email=email,
        subject="Welcome to Spry — You’re in Control 🚀",
        html_content=html_content
    )
