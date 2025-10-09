import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import Optional
from config import config

class EmailService:
    def __init__(self):
        self.smtp_server = config.smtp_server
        self.smtp_port = config.smtp_port
        self.gmail_user = config.gmail_user
        self.gmail_app_password = config.gmail_app_password

    async def initialize(self):
        """Initialize the email service - setup Gmail credentials if needed"""
        if not config.is_gmail_configured():
            print("📧 Gmail not configured. Starting setup...")
            config.setup_gmail_credentials()
            # Reload config after setup
            self.gmail_user = config.gmail_user
            self.gmail_app_password = config.gmail_app_password
        else:
            print("✅ Gmail configuration found")

    async def send_email(self, to_email: str, subject: str, message: str, from_name: Optional[str] = None):
        """
        Send an email using Gmail SMTP

        Args:
            to_email: Recipient email address
            subject: Email subject
            message: Email body content
            from_name: Optional sender name
        """
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
            server.starttls()  # Secure the connection

            # Login
            server.login(self.gmail_user, self.gmail_app_password)

            # Send email
            text = msg.as_string()
            server.sendmail(self.gmail_user, to_email, text)

            # Close connection
            server.quit()

            print(f"✅ Email sent successfully to {to_email}")
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
            error_msg = f"❌ Unexpected error sending email: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    async def test_connection(self) -> bool:
        """Test Gmail SMTP connection"""
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.gmail_user, self.gmail_app_password)
            server.quit()
            return True
        except Exception as e:
            print(f"❌ Connection test failed: {str(e)}")
            return False