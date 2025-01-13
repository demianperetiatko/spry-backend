from utils.send_message import send_email
def send_invitation(email: str):
    send_email(
        to_email=email,
        subject="Welcome to SPTY!",
        html_content="""
            <h1>Welcome to SPTY!</h1>
            <p>You have been invited to join SPTY.</p>
            <p>
                Please click the link below to log in and get started:
                <br>
                <a href=\"https://app.spryplan.com/login\" target=\"_blank\">Log In</a>
            </p>
            <p>If you have any questions, feel free to contact us.</p>
        """
    )