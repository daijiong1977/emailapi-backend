"""Email provider factory for creating appropriate email service instances."""

from typing import Optional
import os

from email_provider import EmailProvider
from providers.gmail_provider import GmailProvider
from providers.ses_provider import SESProvider


class EmailProviderFactory:
    """Factory for creating email provider instances."""

    @staticmethod
    def create_provider(provider_type: Optional[str] = None) -> EmailProvider:
        """Create an email provider instance based on configuration.
        
        Args:
            provider_type: Provider type ('gmail' or 'ses'). 
                          If None, reads from EMAIL_PROVIDER env var.
                          Defaults to 'gmail' if not specified.
        
        Returns:
            EmailProvider instance
            
        Raises:
            ValueError: If provider type is not supported
        """
        if provider_type is None:
            provider_type = os.getenv('EMAIL_PROVIDER', 'gmail').lower()
        
        provider_type = provider_type.lower().strip()
        
        if provider_type == 'gmail':
            return GmailProvider()
        elif provider_type in ('ses', 'amazon-ses', 'aws-ses'):
            return SESProvider()
        else:
            raise ValueError(
                f"Unsupported email provider: {provider_type}. "
                f"Supported providers: gmail, ses"
            )

    @staticmethod
    def get_available_providers() -> list[str]:
        """Get list of available provider names."""
        return ['gmail', 'ses']
