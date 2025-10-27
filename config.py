import os
from typing import Optional
from dotenv import load_dotenv
from mail_config_store import load_mail_config

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    def __init__(self):
        # Load configuration from mail_config.json (with fallback to env vars)
        mail_config = load_mail_config()
        
        # Mail provider configuration
        self.mail_provider: str = mail_config.get('mail_provider') or os.getenv('MAIL_PROVIDER', 'gmail')
        self.mail_from: Optional[str] = mail_config.get('mail_from') or os.getenv('MAIL_FROM')
        
        # Gmail configuration
        self.gmail_user: Optional[str] = mail_config.get('gmail_user') or os.getenv('GMAIL_USER')
        self.gmail_app_password: Optional[str] = mail_config.get('gmail_app_password') or os.getenv('GMAIL_APP_PASSWORD')
        self.smtp_server: str = 'smtp.gmail.com'
        self.smtp_port: int = 587
        
        # AWS SES configuration
        self.aws_access_key_id: Optional[str] = mail_config.get('aws_access_key_id') or os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key: Optional[str] = mail_config.get('aws_secret_access_key') or os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region: Optional[str] = mail_config.get('aws_region') or os.getenv('AWS_REGION')

    def is_gmail_configured(self) -> bool:
        """Check if Gmail credentials are configured"""
        return bool(self.gmail_user and self.gmail_app_password)
    
    def is_ses_configured(self) -> bool:
        """Check if AWS SES credentials are configured"""
        return bool(self.aws_access_key_id and self.aws_secret_access_key and self.aws_region)

    def setup_gmail_credentials(self):
        """Interactive setup for Gmail credentials"""
        print("🔧 Gmail Configuration Setup")
        print("=" * 40)

        if not self.gmail_user:
            self.gmail_user = input("Enter your Gmail address: ").strip()
            if not self.gmail_user:
                raise ValueError("Gmail address is required")

        if not self.gmail_app_password:
            print("\n📝 To get your Gmail App Password:")
            print("1. Go to https://myaccount.google.com/security")
            print("2. Enable 2-Factor Authentication if not already enabled")
            print("3. Go to 'App passwords' section")
            print("4. Generate a new app password for 'Mail'")
            print("5. Copy the 16-character password (ignore spaces)")
            print()
            self.gmail_app_password = input("Enter your Gmail App Password: ").strip()
            if not self.gmail_app_password:
                raise ValueError("App password is required")

        # Save to .env file
        self._save_to_env_file()

        print("✅ Gmail configuration saved successfully!")
        return True

    def _save_to_env_file(self):
        """Save credentials to .env file"""
        env_content = f"""# Gmail Configuration
GMAIL_USER={self.gmail_user}
GMAIL_APP_PASSWORD={self.gmail_app_password}
"""
        with open('.env', 'w') as f:
            f.write(env_content)

        # Set restrictive permissions on .env file
        os.chmod('.env', 0o600)

# Global config instance
config = Config()