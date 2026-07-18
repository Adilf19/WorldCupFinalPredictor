"""TLS SMTP delivery for owner login codes."""

import smtplib
from email.message import EmailMessage

from api.config import ApiSettings


class EmailDeliveryNotConfigured(RuntimeError):
    pass


class OwnerCodeEmailSender:
    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings

    def send(self, *, recipient: str, code: str) -> None:
        if not all(
            (
                self.settings.smtp_host,
                self.settings.smtp_username,
                self.settings.smtp_password,
                self.settings.smtp_from,
            )
        ):
            raise EmailDeliveryNotConfigured(
                "SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM are required"
            )
        message = EmailMessage()
        message["Subject"] = "Your World Cup Predictor owner code"
        message["From"] = self.settings.smtp_from
        message["To"] = recipient
        message.set_content(
            f"Your verification code is {code}. It expires in 10 minutes.\n\n"
            "If you did not request it, you can ignore this email."
        )
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
