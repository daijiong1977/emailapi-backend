"""Abstract email provider interface and implementations for Gmail and Amazon SES.

This module defines a base EmailProvider protocol and concrete implementations
for different email services, allowing the application to switch between
email engines via configuration.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class EmailMessage:
    """Email message data structure."""
    to_email: str
    subject: str
    message: str
    from_name: Optional[str] = None


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the email provider with necessary setup."""
        pass

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        from_name: Optional[str] = None
    ) -> bool:
        """Send an email.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            message: Email body content
            from_name: Optional sender name
            
        Returns:
            True if email was sent successfully
            
        Raises:
            Exception: If email sending fails
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection to the email service.
        
        Returns:
            True if connection is successful
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured.
        
        Returns:
            True if all required credentials are present
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of the email provider."""
        pass
