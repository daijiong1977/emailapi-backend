# Email API Configuration Guide

## Choosing an Email Provider

The Email API service supports two email providers:

- **Gmail SMTP** (default)
- **Amazon SES**

Set the provider using the `EMAIL_PROVIDER` environment variable in your `.env` file:

```bash
# For Gmail (default)
EMAIL_PROVIDER=gmail

# For Amazon SES
EMAIL_PROVIDER=ses
```

## Gmail Configuration

### Environment Variables

```bash
GMAIL_USER=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

### Setup Steps

1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password at https://myaccount.google.com/apppasswords
3. Add credentials to `/opt/emailapi/.env`
4. Restart the service

For detailed Gmail setup, see the main README.md.

## Amazon SES Configuration

### Prerequisites

1. AWS Account with SES access
2. Verified sender email address or domain in SES
3. SES moved out of sandbox mode (for production)
4. IAM user with `ses:SendEmail` permission

### Environment Variables

```bash
# Required
EMAIL_PROVIDER=ses
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
SES_FROM_EMAIL=verified-sender@yourdomain.com

# Optional
SES_CONFIGURATION_SET=your-configuration-set-name
```

### AWS IAM Policy

Create an IAM user with this minimal policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

### SES Setup Steps

1. **Verify your email/domain in SES:**
   ```bash
   aws ses verify-email-identity --email-address sender@yourdomain.com
   ```

2. **Request production access** (if needed):
   - Go to AWS SES console → Account dashboard
   - Request production access to send to any email address

3. **Add credentials to `.env`:**
   ```bash
   echo "EMAIL_PROVIDER=ses" >> /opt/emailapi/.env
   echo "AWS_REGION=us-east-1" >> /opt/emailapi/.env
   echo "AWS_ACCESS_KEY_ID=YOUR_KEY" >> /opt/emailapi/.env
   echo "AWS_SECRET_ACCESS_KEY=YOUR_SECRET" >> /opt/emailapi/.env
   echo "SES_FROM_EMAIL=verified@yourdomain.com" >> /opt/emailapi/.env
   ```

4. **Install boto3** (if not already installed):
   ```bash
   sudo -u emailapi /opt/emailapi/venv/bin/pip install boto3
   ```

5. **Restart the service:**
   ```bash
   sudo systemctl restart emailapi
   sudo journalctl -u emailapi -n 50 --no-pager
   ```

### Testing SES Configuration

Check the service logs for successful initialization:

```bash
sudo journalctl -u emailapi -n 20 --no-pager | grep -i ses
```

You should see:
```
✅ Amazon SES configuration found
✅ Email provider initialized: Amazon SES
```

Test sending an email:

```bash
curl -X POST https://emailapi.6ray.com/send-email \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "to_email": "recipient@example.com",
    "subject": "SES Test",
    "message": "Testing Amazon SES integration",
    "from_name": "Test Sender"
  }'
```

## Switching Between Providers

To switch providers:

1. Update `EMAIL_PROVIDER` in `.env`
2. Ensure the new provider's credentials are configured
3. Restart the service: `sudo systemctl restart emailapi`

The service will automatically use the configured provider for all email operations.

## Troubleshooting

### Gmail Issues

- **Authentication Error**: Verify app password is correct (16 chars, no spaces)
- **Connection Timeout**: Check firewall settings, ensure port 587 is open

### SES Issues

- **Email address not verified**: Verify sender email in SES console
- **Sandbox mode restrictions**: Request production access in SES console
- **AWS credentials error**: Verify IAM user has `ses:SendEmail` permission
- **boto3 not found**: Install with `pip install boto3`

### General

Check provider status:
```bash
curl -s https://emailapi.6ray.com/config/status
```

View recent logs:
```bash
sudo journalctl -u emailapi -n 100 --no-pager
```
