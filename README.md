# Email API Service

A FastAPI-based email service that receives email requests from iOS applications and sends emails using **Gmail SMTP** or **Amazon SES**.

## Features

- 🚀 FastAPI backend for high-performance email sending
- 📧 **Multiple Email Providers**: Gmail SMTP or Amazon SES (switchable via admin panel)
- 🔐 Secure credential management with environment variables
- 📱 RESTful API designed for iOS app integration
- ⚡ Asynchronous email sending with background tasks
- 🏥 Health check endpoints
- 📝 Comprehensive logging and error handling
- 🎛️ **Admin Panel** for provider configuration and testing
- ✅ **Test Connection** and **Send Test Email** features

## Prerequisites

- Python 3.8+
- **Email Provider** (choose one):
  - **Gmail**: Account with 2FA enabled + App Password
  - **Amazon SES**: AWS account with SES enabled + IAM user with SES permissions

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd email-api-service
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Email Provider

#### Option A: Use Admin Panel (Recommended)

1. Start the application:
   ```bash
   python main.py
   ```

2. Visit the admin panel: `http://localhost:8002/admin/config`
   - Default password: `771008`

3. **Select your email provider** (Gmail or Amazon SES)

4. **For Gmail**:
   - Enter Gmail address
   - Enter App Password (16 characters, no spaces)
   - Generate at: [Google App Passwords](https://myaccount.google.com/apppasswords)

5. **For Amazon SES**:
   - Enter AWS Region (e.g., `us-east-2`)
   - Enter AWS Access Key ID
   - Enter AWS Secret Access Key
   - Enter verified sender email (must be verified in SES)

6. Click **"Test Connection"** to verify credentials

7. Click **"Send Test Email"** to send an actual test email

#### Option B: Manual Configuration

Create a `.env` file:

**For Gmail:**
```bash
EMAIL_PROVIDER=gmail
GMAIL_USER=your-gmail@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

**For Amazon SES:**
```bash
EMAIL_PROVIDER=ses
AWS_REGION=us-east-2
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
SES_FROM_EMAIL=verified@yourdomain.com
# Optional:
# SES_CONFIGURATION_SET=my-config-set
```

### 4. Run the Application

```bash
# Development
python main.py

# Or with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8002
```

## API Endpoints

### Send Email
```http
POST /send-email
Content-Type: application/json
X-API-Key: <your-api-key>

```json
{
  "to_email": "self@6ray.com",
  "subject": "Test Email",
  "message": "Hello from the Email API!",
  "from_name": "Your App"
}
```
```

**Response:**
```json
{
  "success": true,
  "message": "Email queued for sending",
  "email_id": "self@6ray.com_123456789"
}
```

### Send Bulk Email

Send the same email to multiple recipients in one API call:

```http
POST /send-bulk-email
Content-Type: application/json
X-API-Key: <your-api-key>
```

**Request:**
```json
{
  "to_emails": [
    "recipient1@example.com",
    "recipient2@example.com",
    "recipient3@example.com"
  ],
  "subject": "Newsletter Update",
  "message": "Hello everyone! This is our latest update.",
  "from_name": "Newsletter Team"
}
```

**Response:**
```json
{
  "total": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "email": "recipient1@example.com",
      "status": "success"
    },
    {
      "email": "recipient2@example.com",
      "status": "success"
    },
    {
      "email": "recipient3@example.com",
      "status": "success"
    }
  ]
}
```

**Rate Limits:**
- **Gmail SMTP**: ~500 emails/day
- **Amazon SES Sandbox**: 200 emails/day (recipients must be verified)
- **Amazon SES Production**: Variable (request quota increase via AWS Console)

**Best Practices:**
- For large lists (>100), consider batching multiple requests
- Check the `results` array for per-recipient status
- Failed sends don't stop the batch - review `successful` vs `failed` counts
- All recipients must pass domain policy checks or entire batch fails

### Client Bootstrap
```http
POST /client/bootstrap
Content-Type: application/json
```

**Request:**
```json
{
  "device_id": "ios-device-uuid",
  "display_name": "Alice’s iPhone"
}
```

**Response:**
```json
{
  "device_id": "ios-device-uuid",
  "username": "ios-abc123def456",
  "api_key": "<key_id>.<secret>"
}
```

The endpoint is idempotent: the same `device_id` receives the same API key on subsequent calls. If a device is disabled by an administrator the route returns HTTP 403.

> Prerequisites: set `DEVICE_KEY_SECRET` (recommended) or `ADMIN_TOKEN` in your `.env` so the server can encrypt the issued keys at rest.

### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "email-api"
}
```

### Configuration Status
```http
GET /config/status
```

**Response:**
```json
{
  "email_provider": "Amazon SES",
  "configured": true,
  "message": "Amazon SES is configured and ready"
}
```

### Admin Panel
```http
GET /admin/config
```

Access the admin panel at `https://emailapi.6ray.com/admin/config` to:
- Switch between Gmail and Amazon SES
- Configure email provider credentials
- Test connection without sending emails
- Send test emails to verify end-to-end delivery

## Email Provider Setup

### Gmail Setup

1. **Enable 2-Factor Authentication**:
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Enable 2FA if not already enabled

2. **Generate App Password**:
   - Go to [App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" → "Other (custom name)" → Enter "Email API"
   - Copy the 16-character password

3. **Configure via Admin Panel** or add to `.env`:
   ```bash
   EMAIL_PROVIDER=gmail
   GMAIL_USER=your@gmail.com
   GMAIL_APP_PASSWORD=abcdabcdabcdabcd
   ```

For detailed Gmail setup, see: [`EMAIL_PROVIDER_CONFIG.md`](EMAIL_PROVIDER_CONFIG.md)

### Amazon SES Setup

1. **Create/Configure IAM User**:
   - User needs `ses:SendEmail`, `ses:SendRawEmail`, `ses:GetSendQuota` permissions
   - Generate access key and secret key

2. **Verify Sender Email**:
   - In AWS SES Console (us-east-2 or your region)
   - Go to "Verified identities" → "Create identity"
   - Verify your sender email address

3. **Configure via Admin Panel** or add to `.env`:
   ```bash
   EMAIL_PROVIDER=ses
   AWS_REGION=us-east-2
   AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
   AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   SES_FROM_EMAIL=verified@yourdomain.com
   ```

4. **Request Production Access** (optional):
   - By default, SES is in sandbox mode (can only send to verified addresses)
   - Request production access in AWS SES Console for unrestricted sending

For detailed SES setup with IAM policies, see: [`SES_IAM_SETUP.md`](SES_IAM_SETUP.md)

## Testing Your Configuration

### Using Admin Panel (Easiest)

1. Visit: `https://emailapi.6ray.com/admin/config`
2. Click **"Test Connection"** - Verifies credentials without sending email
3. Click **"Send Test Email"** - Sends actual test email to your address

### Using API

```bash
# Get an API key
curl -X POST https://emailapi.6ray.com/client/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"device_id":"test-device-001"}'

# Send test email
curl -X POST https://emailapi.6ray.com/send-email \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -d '{
    "to_email": "your@email.com",
    "subject": "Test Email",
    "message": "Hello from Email API!"
  }'
```

## Deployment on Amazon EC2 (Red Hat 10)

### One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/daijiong1977/emailapi-backend/main/deploy/install-emailapi.sh -o install-emailapi.sh \
  && sudo bash install-emailapi.sh -d emailapi.6ray.com -r https://github.com/daijiong1977/emailapi-backend.git
```

Note: The installer does not install Certbot; HTTPS/SSL is assumed to be handled externally on this host. If you need to provision certificates later, use your existing method and reload Nginx.

After install, edit `/opt/emailapi/.env` with your email provider credentials:

**For Gmail:**
```bash
sudo -u emailapi nano /opt/emailapi/.env
# Add:
EMAIL_PROVIDER=gmail
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=abcdabcdabcdabcd
```

**For Amazon SES:**
```bash
sudo -u emailapi nano /opt/emailapi/.env
# Add:
EMAIL_PROVIDER=ses
AWS_REGION=us-east-2
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
SES_FROM_EMAIL=verified@yourdomain.com
```

Then restart:
```bash
sudo systemctl restart emailapi
```

### Maintenance scripts

- Update to latest code and dependencies:
  ```bash
  sudo bash /opt/emailapi/deploy/update-emailapi.sh
  ```
  Optionally specify a branch:
  ```bash
  sudo bash /opt/emailapi/deploy/update-emailapi.sh main
  ```

- Uninstall everything:
  ```bash
  sudo bash /opt/emailapi/deploy/uninstall-emailapi.sh
  ```

### Restarting the service

After updating code or configuration, restart the daemon and confirm it comes back clean:

```bash
sudo systemctl restart emailapi
sudo systemctl status emailapi
sudo journalctl -u emailapi -n 50 --no-pager
```

If new Python dependencies were added (for example `cryptography` for `/client/bootstrap`), refresh the virtualenv first:

```bash
sudo -u emailapi /opt/emailapi/venv/bin/pip install -r /opt/emailapi/requirements.txt
```

### Gmail configuration helper

The installer will launch an interactive Gmail setup as the last step.
You can run it any time later to update credentials and test the SMTP login:

```bash
sudo -u emailapi bash /opt/emailapi/deploy/config-gmail.sh
```

### Admin Config Panel

A simple password-protected web UI is available (default password `771008`). You can change it by setting `PANEL_PASSWORD` in `/opt/emailapi/.env`.

- Open: `https://emailapi.6ray.com/admin/config`
- Features: set Gmail, manage allow/block domains, create per-user keys, rotate admin token.

### API key configuration

Set API_KEY in `/opt/emailapi/.env` and restart the service. All POST /send-email requests must include:

```
X-API-Key: <your-api-key>
```

### Per-user API keys (optional, more secure)

This service also supports per-user API keys stored in a local SQLite DB. Enable by keeping defaults:

- API_KEYS_DB=/opt/emailapi/api_keys.db
- ADMIN_TOKEN=<random>

Create a user key (admin-only):

```bash
curl -X POST https://emailapi.6ray.com/admin/keys/create \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $(grep ^ADMIN_TOKEN= /opt/emailapi/.env | cut -d= -f2)" \
  -d '{"username":"ios-client-1"}'
```

The response returns a client key in the form `key_id.secret`. Give this full string to the iOS client. The client will use it as the X-API-Key header.

List keys (admin-only):

```bash
curl -s https://emailapi.6ray.com/admin/keys \
  -H "X-Admin-Token: $(grep ^ADMIN_TOKEN= /opt/emailapi/.env | cut -d= -f2)"
```

Revoke a key (admin-only):

```bash
curl -X POST https://emailapi.6ray.com/admin/keys/revoke/<key_id> \
  -H "X-Admin-Token: $(grep ^ADMIN_TOKEN= /opt/emailapi/.env | cut -d= -f2)"
```

### 1. Launch EC2 Instance
- Choose Red Hat Enterprise Linux 10 AMI
- Configure security groups (allow port 8002 for API, 22 for SSH)

### 2. Install Dependencies
```bash
# Update system
sudo dnf update -y

# Install Python 3.9+
sudo dnf install python39 python39-pip -y

# Install git
sudo dnf install git -y
```

### 3. Deploy Application
```bash
# Clone repository
git clone <your-repo-url>
cd email-api-service

# Run the automated setup script
./setup.sh

# Or manually:
# python3 -m venv venv
# source venv/bin/activate
# pip install -r requirements.txt

# Configure Gmail credentials
# Edit .env file with your credentials or run the app to be prompted

# Run the application
source venv/bin/activate
python main.py
```

### 4. Use Systemd for Production
Create a systemd service file `/etc/systemd/system/email-api.service`:

```ini
[Unit]
Description=Email API Service
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/email-api-service
ExecStart=/home/ec2-user/email-api-service/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl enable email-api
sudo systemctl start email-api
sudo systemctl status email-api
```

### 5. Configure Nginx (Optional)
For production deployment with Nginx as reverse proxy:

```nginx
# /etc/nginx/conf.d/email-api.conf
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## iOS Integration

### Swift Example
```swift
struct EmailRequest: Codable {
    let toEmail: String
    let subject: String
    let message: String
    let fromName: String?
}

func sendEmail(request: EmailRequest) async throws -> Bool {
    let url = URL(string: "http://your-ec2-instance:8002/send-email")!
    var urlRequest = URLRequest(url: url)
    urlRequest.httpMethod = "POST"
    urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

    let jsonData = try JSONEncoder().encode(request)
    urlRequest.httpBody = jsonData

    let (data, response) = try await URLSession.shared.data(for: urlRequest)

    guard let httpResponse = response as? HTTPURLResponse,
          httpResponse.statusCode == 200 else {
        throw URLError(.badServerResponse)
    }

    let result = try JSONDecoder().decode(EmailResponse.self, from: data)
    return result.success
}
```

## Security Considerations

- 🔐 App passwords provide secure access without exposing main password
- 🚫 Never commit `.env` file to version control
- 🔒 Use HTTPS in production (consider SSL termination)
- 📝 Implement rate limiting for API endpoints
- 👤 Validate email addresses and sanitize input

## Smoke Testing from macOS

The repo includes `ios_smoke_test.py` to exercise the live service from a workstation.

1. **Provision a client key (idempotent)**

  ```bash
  curl -s -X POST https://emailapi.6ray.com/client/bootstrap \
      -H "Content-Type: application/json" \
      -d '{"device_id":"mac-smoke-000001","display_name":"Mac Smoke"}' \
    | python -m json.tool
  ```

  Save the returned `api_key` (format `key_id.secret`). A later call with the same `device_id` returns the same key.

2. **Run the smoke script**

  ```bash
   python ios_smoke_test.py \
     --base-url https://emailapi.6ray.com \
     --api-key <key_id.secret-from-bootstrap> \
    --to-email dd@6ray.com \
    --from-name "Mac Smoke" \
    --subject "Bootstrap smoke" \
    --message "Automated smoke test from mac"
  ```

  The script checks `/health`, `/config/status`, and queues a test email via `/send-email`.

Tips:

- Omit `--api-key` and add `--bootstrap` to let the script call `/client/bootstrap` automatically (stores the key in `~/.email_api_bootstrap.json` by default).
- Set environment variables (`EMAIL_API_BASE_URL`, `EMAIL_API_KEY`, etc.) to avoid passing secrets directly on the command line.
- Rotate the bootstrap key in the admin UI if you no longer need it.

## Troubleshooting

### Common Issues

1. **SMTP Authentication Error**
   - Verify app password is correct (16 characters, no spaces)
   - Ensure 2FA is enabled on Gmail account
   - Check if app password was recently regenerated

2. **Connection Timeout**
   - Verify internet connectivity
   - Check firewall settings on EC2
   - Ensure Gmail SMTP is not blocked

3. **Port Already in Use**
   - Kill existing processes: `sudo lsof -ti:8002 | xargs kill -9`
   - Change port in configuration

### Logs
Check application logs for detailed error information:
```bash
# View recent logs
journalctl -u email-api -f

# View application stdout
sudo systemctl status email-api
```

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest httpx

# Run tests
pytest
```

### API Documentation
Access interactive API documentation at `http://localhost:8002/docs` when running locally.

## Documentation

- **[EMAIL_PROVIDER_CONFIG.md](EMAIL_PROVIDER_CONFIG.md)** - Detailed guide for configuring Gmail and Amazon SES
- **[SES_IAM_SETUP.md](SES_IAM_SETUP.md)** - AWS IAM user setup and permissions for SES
- **[ADMIN_PANEL_GUIDE.md](ADMIN_PANEL_GUIDE.md)** - Admin panel usage and features
- **[frontend.md](frontend.md)** - iOS client integration guide with Swift examples

## Architecture

### Email Provider Abstraction

The service uses a provider pattern allowing easy switching between email services:

```
EmailService (Facade)
    ↓
EmailProviderFactory
    ↓
    ├─ GmailProvider (SMTP)
    └─ SESProvider (AWS SDK)
```

**Benefits:**
- Switch providers via environment variable or admin panel
- Add new providers without changing core logic
- Test each provider independently
- Provider-specific configuration isolation

## License

MIT License - see LICENSE file for details.