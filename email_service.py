"""Email service that delegates to configured email provider (Gmail or SES).

This service acts as a facade, routing email operations to the appropriate
provider based on configuration.
"""

from typing import Optional
from email_factory import EmailProviderFactory
from email_provider import EmailProvider


class EmailService:
    """Email service that uses pluggable email providers."""
    
    def __init__(self, provider: Optional[EmailProvider] = None):
        """Initialize email service with a provider.
        
        Args:
            provider: EmailProvider instance. If None, creates one from config.
        """
        self.provider = provider or EmailProviderFactory.create_provider()

    async def initialize(self):
        """Initialize the email service provider."""
        await self.provider.initialize()
        provider_name = self.provider.get_provider_name()
        if self.provider.is_configured():
            print(f"✅ Email provider initialized: {provider_name}")
        else:
            print(f"⚠️ Email provider not fully configured: {provider_name}")

    async def send_email(self, to_email: str, subject: str, message: str, from_name: Optional[str] = None):
        """Send an email using the configured provider.

        Args:
            to_email: Recipient email address
            subject: Email subject
            message: Email body content
            from_name: Optional sender name
        """
        return await self.provider.send_email(to_email, subject, message, from_name)

    async def test_connection(self) -> bool:
        """Test the email provider connection."""
        return await self.provider.test_connection()

    def get_provider_name(self) -> str:
        """Get the name of the currently configured provider."""
        return self.provider.get_provider_name()
