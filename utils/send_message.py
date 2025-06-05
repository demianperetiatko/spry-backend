import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def send_email(to_email, subject, html_content, from_email='hello@spryplan.com'):
    try:
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content)
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)

    except Exception as e:
        print("Send Email (SendGridAPIClient) :", e)


def send_user_invitation(email: str):
    send_email(
        to_email=email,
        subject="✨ You’re Invited to Spry! ✨",
        html_content="""
            <h1>Welcome aboard!</h1>
            <p>You’ve been invited to join the team’s new tool that’s designed to make your meetings more productive and exciting.</p>
            <p>No more boring, aimless meetings – with Spry, every conversation counts.</p>
            <p>🚀 Ready to dive in? <a href="https://app.spryplan.com/login" target="_blank">Start analyzing your next meetings</a> — it’s quick, easy, and shows you how Spry can help make your meetings more organized and meaningful.</p>
            <p>Let’s turn meetings into something to look forward to! 🎉</p>
        """
    )


def send_agenda_request(email: str, calendar_event_link: str = "#"):
    send_email(
        to_email=email,
        subject="🎯 Agenda Request for Your Upcoming Meeting",
        html_content=f"""
            <p>Hi there – someone invited to your upcoming meeting was hoping to see an agenda in advance.</p>
            <p>Even a short agenda helps your team prepare, stay focused, and make faster decisions. It also helps you lead the meeting with more clarity and avoid time-consuming follow-ups.</p>
            <p>If you have a moment, here’s a quick format that’s easy to copy, paste, and adjust for your needs:</p>
            <h3>📋 Agenda Template</h3>
            <b>Main Goal</b><br>
            What should we accomplish by the end of the meeting?<br><br>
            <b>Talking Points</b><br>
            [Topic 1]<br><br>
            [Topic 2]<br><br>
            [Topic 3]<br><br>
            <b>Prep Needed</b><br>
            [Document or context to review]<br><br>
            [Anything to bring or prepare]<br><br>
            <p>Thanks for helping make the meeting more useful and productive for everyone 💛</p>
            <hr>
            <p>This request was sent anonymously via Spry.</p>
            <p>
                👉 <a href="{calendar_event_link}" target="_blank">Go to the calendar event</a>
            </p>
            <p><i>Powered by Spry</i></p>
        """
    )


def send_admin_invitation(email: str):
    send_email(
        to_email=email,
        subject="Welcome to Spry — You’re in Control 🚀",
        html_content="""
            <h1>Welcome to Spry — You’re in Control 🚀</h1>
            <p>Hi there,</p>
            <p>Welcome aboard — we're excited to have you as the first admin for your team on Spry!</p>
            <p>You’re now set up to create your organization, build teams, and invite your colleagues to start making meetings more intentional and productive.</p>
            <h3>🎯 As an admin, you can now:</h3>
            <ul>
                <li>Set up your organization’s name and structure</li>
                <li>Create teams and assign roles</li>
                <li>Invite others to join and start using Spry</li>
            </ul>
            <p>You’re in the perfect spot to shape how your team works together — with less chaos, more clarity, and better conversations.</p>
            <p>Need help? Just hit reply if you have any questions.</p>
            <p>Let’s build something great together,<br><b>The Spry Team</b></p>
        """
    )
