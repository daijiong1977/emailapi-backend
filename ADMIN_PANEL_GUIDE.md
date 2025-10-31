# Admin Panel Screenshots & Usage Guide

## New Email Provider Configuration

The admin panel now includes a comprehensive email provider configuration interface that allows you to choose between Gmail SMTP and Amazon SES.

## Features

### 1. Email Provider Selection
- **Location**: Top of the admin panel
- **Options**: 
  - Gmail SMTP (default)
  - Amazon SES
- **Behavior**: Dynamic form that shows/hides relevant configuration based on selection

### 2. Gmail Configuration Section
Displays when "Gmail SMTP" is selected:
- Gmail Address
- App Password (with link to Google App Passwords)
- Helpful tooltips for each field

### 3. Amazon SES Configuration Section
Displays when "Amazon SES" is selected:
- AWS Region (default: us-east-1)
- AWS Access Key ID
- AWS Secret Access Key
- SES From Email (verified sender)
- SES Configuration Set (optional)
- Detailed help text for each field

### 4. Existing Features Preserved
- Recipient Domain Policy (Allow/Block lists)
- iOS Client API Key creation
- Seed Users management
- API Keys listing
- Admin Token rotation

## Usage Instructions

### Accessing the Admin Panel

1. Navigate to: `https://emailapi.6ray.com/admin/config`
2. Enter the panel password (default: `771008`)
3. Configure your preferred email provider

### Switching from Gmail to Amazon SES

1. **Select Provider**:
   - Choose "Amazon SES" from the dropdown
   - Click "Save Provider Selection"

2. **Configure SES**:
   - Fill in AWS credentials:
     - AWS Region (e.g., `us-east-1`)
     - AWS Access Key ID
     - AWS Secret Access Key
     - SES From Email (must be verified in SES)
   - Optional: Add SES Configuration Set
   - Click "Save Amazon SES Settings"

3. **Restart Service**:
   ```bash
   sudo systemctl restart emailapi
   ```

4. **Verify**:
   ```bash
   curl -s https://emailapi.6ray.com/config/status
   ```
   
   Should show:
   ```json
   {
     "email_provider": "Amazon SES",
     "configured": true,
     "message": "Amazon SES is configured and ready"
   }
   ```

### Switching from SES back to Gmail

1. **Select Provider**:
   - Choose "Gmail SMTP" from the dropdown
   - Click "Save Provider Selection"

2. **Configure Gmail** (if not already done):
   - Enter Gmail address
   - Enter App Password
   - Click "Save Gmail Settings"

3. **Restart Service**:
   ```bash
   sudo systemctl restart emailapi
   ```

## Important Notes

- **Service Restart Required**: Changing the email provider requires a service restart to take effect
- **Configuration Persistence**: All settings are saved to `.env` file with secure permissions
- **Validation**: The panel validates provider selection and shows helpful error messages
- **Security**: Passwords/secret keys are not displayed after saving (shown as bullets)
- **Backward Compatible**: Defaults to Gmail if `EMAIL_PROVIDER` is not set

## Admin Panel Layout

```
Email API Configuration
├── [Success/Error Messages]
├── Email Provider Selection
│   ├── Provider Dropdown (Gmail/SES)
│   └── Save Button
├── Gmail SMTP Configuration (conditional)
│   ├── Gmail Address
│   ├── App Password
│   └── Save Gmail Settings
├── Amazon SES Configuration (conditional)
│   ├── AWS Region
│   ├── AWS Access Key ID
│   ├── AWS Secret Access Key
│   ├── SES From Email
│   ├── SES Configuration Set
│   └── Save Amazon SES Settings
├── Recipient Domain Policy
├── Create iOS Client API Key
├── Seed Users Management
├── Existing Keys List
└── Admin Token Rotation
```

## Technical Details

### Dynamic Form Behavior

The panel uses JavaScript to toggle between Gmail and SES configuration forms:

- On page load, shows the currently configured provider
- When provider dropdown changes, instantly switches forms
- Only the active provider's form is visible
- Smooth user experience without page reload

### API Endpoints

New endpoints added:
- `POST /admin/config/provider` - Save email provider selection
- `POST /admin/config/ses` - Save Amazon SES configuration
- Updated `POST /admin/config/gmail` - Now shows restart reminder
- Updated `GET /config/status` - Returns current provider info

### Configuration Storage

All settings stored in `/opt/emailapi/.env`:

```bash
# Email Provider Selection
EMAIL_PROVIDER=ses  # or 'gmail'

# Gmail Settings (if using Gmail)
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=yourapppassword

# SES Settings (if using SES)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
SES_FROM_EMAIL=verified@yourdomain.com
SES_CONFIGURATION_SET=my-config-set  # optional
```
