# Amazon SES IAM User Setup Guide

## Problem
Your IAM user `news` (arn:aws:iam::802594764990:user/news) doesn't have permission to perform SES operations.

## Solution: Add SES Permissions to IAM User

### Option 1: Using AWS Console (Recommended)

1. **Go to IAM Console**
   - Visit: https://console.aws.amazon.com/iam/
   - Click "Users" in the left sidebar
   - Click on user "news"

2. **Add Inline Policy**
   - Click "Add permissions" → "Create inline policy"
   - Click "JSON" tab
   - Paste this policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendEmail",
                "ses:SendRawEmail",
                "ses:GetSendQuota",
                "ses:GetSendStatistics"
            ],
            "Resource": "*"
        }
    ]
}
```

3. **Name and Save**
   - Click "Next"
   - Policy name: `EmailAPISESAccess`
   - Click "Create policy"

### Option 2: Using AWS CLI

```bash
# Create policy file
cat > ses-policy.json <<'EOF'
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendEmail",
                "ses:SendRawEmail",
                "ses:GetSendQuota",
                "ses:GetSendStatistics"
            ],
            "Resource": "*"
        }
    ]
}
EOF

# Attach to user
aws iam put-user-policy \
    --user-name news \
    --policy-name EmailAPISESAccess \
    --policy-document file://ses-policy.json
```

### Option 3: Use Managed Policy (Quick but gives more permissions)

```bash
aws iam attach-user-policy \
    --user-name news \
    --policy-arn arn:aws:iam::aws:policy/AmazonSESFullAccess
```

## Required Permissions Explained

- **ses:SendEmail** - Send formatted emails
- **ses:SendRawEmail** - Send raw MIME emails (for attachments, HTML, etc.)
- **ses:GetSendQuota** - Check sending limits (used for connection testing)
- **ses:GetSendStatistics** - View sending statistics (optional, for monitoring)

## Verify Sender Email

Before sending emails, you must verify the sender email in SES:

### If SES is in Sandbox Mode (Default)

1. **Verify Sender Email**
   - Go to: https://console.aws.amazon.com/ses/
   - Click "Verified identities"
   - Click "Create identity"
   - Select "Email address"
   - Enter: `news@6ray.com`
   - Click "Create identity"
   - Check your email and click the verification link

2. **Verify Recipient Emails (Sandbox Only)**
   - In sandbox mode, you can only send to verified addresses
   - Verify any test email addresses you want to use
   - OR request production access (see below)

### Request Production Access (Recommended for Production)

1. Go to: https://console.aws.amazon.com/ses/
2. Click "Account dashboard"
3. Click "Request production access"
4. Fill out the form:
   - **Mail type**: Transactional
   - **Use case**: Email API service for iOS app notifications
   - **Compliance**: Yes (follow AWS guidelines)
5. Submit and wait for approval (usually 24 hours)

## After Setup

Once IAM permissions are added and email is verified:

1. **Test Connection** - Should now show: "✅ Connection successful! Amazon SES is properly configured"
2. **Send Test Email** - Should deliver to verified email addresses

## Current Configuration

- **AWS Account**: 802594764990
- **IAM User**: news
- **Region**: us-east-2 (Ohio)
- **From Email**: news@6ray.com (must be verified)

## Troubleshooting

### "User is not authorized to perform: ses:SendEmail"
→ IAM policy not applied yet. Wait a few seconds and try again.

### "Email address is not verified"
→ Verify news@6ray.com in SES console and click verification email link.

### "MessageRejected: Email address is not verified"
→ You're in sandbox mode. Either verify recipient email or request production access.

### "InvalidParameterValue: Missing final '@domain'"
→ Check that SES_FROM_EMAIL is set to a valid email address like news@6ray.com

## Quick Test After Setup

```bash
# From your Mac (after updating IAM permissions)
curl -X POST https://emailapi.6ray.com/admin/config/test-connection \
  -u :771008

# Should return:
# ✅ Connection successful! Amazon SES is properly configured and reachable.
```
