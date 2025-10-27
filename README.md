# Email API Service

A FastAPI-based email service that receives email requests from iOS applications and sends emails using Gmail SMTP with app password authentication.

## Features

- 🚀 FastAPI backend for high-performance email sending
- 📧 Gmail SMTP integration with app password authentication
- 🔐 Secure credential management with environment variables
- 📱 RESTful API designed for iOS app integration
- ⚡ Asynchronous email sending with background tasks
- 🏥 Health check endpoints
- 📝 Comprehensive logging and error handling

## Prerequisites

- Python 3.8+
- Gmail account with 2-Factor Authentication enabled
- Gmail App Password (generated from Google Account settings)

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

### 3. Configure Gmail Credentials

On first run, the application will prompt you to set up Gmail credentials:

```bash
python main.py
```

Or manually create a `.env` file:

```bash
# .env
GMAIL_USER=your-gmail@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

### 4. Run the Application

```bash
# Development
python main.py

# Or with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8002
```

## Mail Configuration

### Configuration Storage

The Email API supports two mail providers: **Gmail** and **Amazon SES**. Configuration can be managed through:

1. **mail_config.json** (recommended) - Secure JSON file for mail provider settings
2. **Environment variables** - Traditional .env file or system environment variables
3. **Admin UI** - Web-based configuration panel at `/admin/config`

### Using mail_config.json

The `mail_config.json` file provides a secure way to store mail provider credentials and settings. The file is automatically created when you save settings through the admin UI.

**File Location:**
- Default: `./mail_config.json` (in the application root)
- Custom: Set `MAIL_CONFIG_PATH` environment variable

**File Structure:**
```json
{
  "mail_provider": "gmail",
  "mail_from": "noreply@example.com",
  "gmail_user": "your-email@gmail.com",
  "gmail_app_password": "your-app-password",
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
  "aws_region": "us-east-1"
}
```

**Security:**
- The file is automatically created with restrictive permissions (mode 0600)
- Secret values (passwords, AWS secret keys) are NOT displayed in the admin UI
- The file should be added to `.gitignore` and never committed to version control
- Consider encrypting the file at rest in production environments

**Configuration Priority:**
The application loads configuration in the following order (highest to lowest priority):
1. Environment variables (e.g., `GMAIL_USER`)
2. `.env` file values
3. `mail_config.json` values

This allows you to override JSON configuration with environment variables when needed.

### Admin Configuration UI

Access the password-protected admin panel at `https://your-domain.com/admin/config` (default password: `771008`).

The admin UI allows you to:
- Select mail provider (Gmail or Amazon SES)
- Configure Gmail SMTP credentials
- Configure AWS SES credentials
- Set mail sender address
- Manage recipient domain policies
- Create and manage API keys

**Note:** When updating credentials through the admin UI:
- Secret fields (passwords, secret keys) are not pre-filled for security
- Leave secret fields blank to keep existing values
- Only provide new values when you want to update them

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
  "gmail_configured": true,
  "message": "Gmail is configured and ready"
}
```

## Gmail Setup Instructions

### 1. Enable 2-Factor Authentication
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Factor Authentication if not already enabled

### 2. Generate App Password
1. Go to [App Passwords](https://myaccount.google.com/apppasswords)
2. Select "Mail" as the app
3. Choose "Other (custom name)" and enter "Email API"
4. Copy the 16-character password (ignore spaces)

### 3. Configure Environment
The app will prompt for credentials on first run, or you can set them manually in the `.env` file.

## Deployment on Amazon EC2 (Red Hat 10)

### One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/daijiong1977/emailapi-backend/main/deploy/install-emailapi.sh -o install-emailapi.sh \
  && sudo bash install-emailapi.sh -d emailapi.6ray.com -r https://github.com/daijiong1977/emailapi-backend.git
```

Note: The installer does not install Certbot; HTTPS/SSL is assumed to be handled externally on this host. If you need to provision certificates later, use your existing method and reload Nginx.

After install, edit `/opt/emailapi/.env` with your Gmail and app password, then:

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

## License

MIT License - see LICENSE file for details.