import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    def __init__(self):
        self.gmail_user: Optional[str] = os.getenv('GMAIL_USER')
        self.gmail_app_password: Optional[str] = os.getenv('GMAIL_APP_PASSWORD')
        self.smtp_server: str = 'smtp.gmail.com'
        self.smtp_port: int = 587

    def is_gmail_configured(self) -> bool:
        """Check if Gmail credentials are configured"""
        return bool(self.gmail_user and self.gmail_app_password)

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