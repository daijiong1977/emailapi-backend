"""Gmail SMTP email provider implementation."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os

from email_provider import EmailProvider


class GmailProvider(EmailProvider):
    """Gmail SMTP email provider."""

    def __init__(self):
        self.smtp_server = 'smtp.gmail.com'
        self.smtp_port = 587
        self.gmail_user: Optional[str] = os.getenv('GMAIL_USER')
        self.gmail_app_password: Optional[str] = os.getenv('GMAIL_APP_PASSWORD')

    async def initialize(self) -> None:
        """Initialize Gmail provider."""
        if self.is_configured():
            print("✅ Gmail configuration found")
        else:
            print("⚠️ Gmail not fully configured")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        from_name: Optional[str] = None
    ) -> bool:
        """Send email via Gmail SMTP."""
        try:
            # Create message
            msg = MIMEMultipart()
            from_display = f"{from_name} <{self.gmail_user}>" if from_name else self.gmail_user
            msg['From'] = from_display
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add message body
            msg.attach(MIMEText(message, 'plain'))

            # Create SMTP connection
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()

            # Login
            server.login(self.gmail_user, self.gmail_app_password)

            # Send email
            text = msg.as_string()
            server.sendmail(self.gmail_user, to_email, text)

            # Close connection
            server.quit()

            print(f"✅ Email sent successfully to {to_email} via Gmail")
            return True

        except smtplib.SMTPAuthenticationError:
            error_msg = "❌ Gmail authentication failed. Please check your credentials."
            print(error_msg)
            raise Exception(error_msg)
        except smtplib.SMTPConnectError:
            error_msg = "❌ Failed to connect to Gmail SMTP server."
            print(error_msg)
            raise Exception(error_msg)
        except smtplib.SMTPException as e:
            error_msg = f"❌ SMTP error: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"❌ Unexpected error sending email via Gmail: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    async def test_connection(self) -> bool:
        """Test Gmail SMTP connection."""
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.gmail_user, self.gmail_app_password)
            server.quit()
            return True
        except Exception as e:
            print(f"❌ Gmail connection test failed: {str(e)}")
            return False

    def is_configured(self) -> bool:
        """Check if Gmail credentials are configured."""
        return bool(self.gmail_user and self.gmail_app_password)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "Gmail"
