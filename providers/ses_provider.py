"""Amazon SES email provider implementation."""

from typing import Optional
import os

from email_provider import EmailProvider

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class SESProvider(EmailProvider):
    """Amazon SES email provider."""

    def __init__(self):
        self.aws_region: Optional[str] = os.getenv('AWS_REGION', 'us-east-1')
        self.aws_access_key_id: Optional[str] = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key: Optional[str] = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.ses_from_email: Optional[str] = os.getenv('SES_FROM_EMAIL')
        self.ses_configuration_set: Optional[str] = os.getenv('SES_CONFIGURATION_SET')
        self.client = None

    async def initialize(self) -> None:
        """Initialize SES provider."""
        if not BOTO3_AVAILABLE:
            print("⚠️ boto3 not installed. Amazon SES provider unavailable.")
            print("   Install with: pip install boto3")
            return

        if not self.is_configured():
            print("⚠️ Amazon SES not fully configured")
            return

        try:
            # Initialize boto3 client
            self.client = boto3.client(
                'ses',
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            )
            print("✅ Amazon SES configuration found")
        except Exception as e:
            print(f"⚠️ Failed to initialize SES client: {str(e)}")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        from_name: Optional[str] = None
    ) -> bool:
        """Send email via Amazon SES."""
        if not BOTO3_AVAILABLE:
            raise Exception("boto3 library not available. Install with: pip install boto3")

        if not self.client:
            raise Exception("SES client not initialized. Call initialize() first.")

        try:
            # Determine sender
            sender = f"{from_name} <{self.ses_from_email}>" if from_name else self.ses_from_email

            # Build email params
            email_params = {
                'Source': sender,
                'Destination': {
                    'ToAddresses': [to_email]
                },
                'Message': {
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': message,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            }

            # Add configuration set if configured
            if self.ses_configuration_set:
                email_params['ConfigurationSetName'] = self.ses_configuration_set

            # Send email
            response = self.client.send_email(**email_params)

            message_id = response.get('MessageId', 'unknown')
            print(f"✅ Email sent successfully to {to_email} via Amazon SES (MessageId: {message_id})")
            return True

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            print(f"❌ SES ClientError [{error_code}]: {error_msg}")
            raise Exception(f"SES error: {error_msg}")
        except NoCredentialsError:
            error_msg = "❌ AWS credentials not found or invalid."
            print(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"❌ Unexpected error sending email via SES: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    async def test_connection(self) -> bool:
        """Test SES connection by checking sending quota."""
        if not BOTO3_AVAILABLE:
            raise Exception("boto3 library not available. Install with: pip install boto3")

        if not self.client:
            raise Exception("SES client not initialized. Call initialize() first or restart the service.")

        try:
            # Get sending quota as a simple connectivity test
            response = self.client.get_send_quota()
            max_send_rate = response.get('MaxSendRate', 0)
            print(f"✅ SES connection test passed (Max send rate: {max_send_rate}/sec)")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            print(f"❌ SES connection test ClientError [{error_code}]: {error_msg}")
            raise Exception(f"AWS SES Error [{error_code}]: {error_msg}")
        except NoCredentialsError as e:
            error_msg = "AWS credentials not found or invalid"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            print(f"❌ SES connection test failed: {str(e)}")
            raise

    def is_configured(self) -> bool:
        """Check if SES credentials are configured."""
        return bool(
            BOTO3_AVAILABLE and
            self.aws_region and
            self.aws_access_key_id and
            self.aws_secret_access_key and
            self.ses_from_email
        )

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "Amazon SES"
