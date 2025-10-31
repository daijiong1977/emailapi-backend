# Email API Service Documentation

## Overview

The Email API Service is a FastAPI-based backend that provides email sending capabilities for iOS applications and web clients. It supports multiple email providers (Gmail SMTP, Amazon SES) with secure credential management and device registration.

**Key Features:**
- 📧 Multiple email providers (Gmail SMTP / Amazon SES)
- 📱 iOS client bootstrap and device registration
- 🔐 API key-based authentication
- ✉️ Single and bulk email sending
- 🎯 Domain-based recipient filtering
- 🔄 Dynamic provider switching via admin panel
- 🏥 Health check endpoints

## Base URL

```
https://emailapi.6ray.com
```

## Authentication

Most endpoints require API key authentication via the `X-API-Key` header:

```
X-API-Key: your-api-key-here
```

## Table of Contents

- [Client Bootstrap](#client-bootstrap)
- [Send Email](#send-email)
- [Send Bulk Email](#send-bulk-email)
- [Health Check](#health-check)
- [Configuration Status](#configuration-status)
- [Error Handling](#error-handling)
- [Admin Endpoints](#admin-endpoints)

---

## Client Bootstrap

Register a new iOS device and obtain an API key for subsequent requests.

### Endpoint

```
POST /client/bootstrap
```

**Authentication:** None required

### Request Body

```json
{
  "device_id": "unique-device-identifier",
  "display_name": "John's iPhone"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `device_id` | String | **Yes** | Unique device identifier (min 8 chars, max 128 chars) |
| `display_name` | String | No | Human-readable device name (max 120 chars) |

### Response

```json
{
  "device_id": "unique-device-identifier",
  "api_key": "generated-api-key-here",
  "username": "ios_device12345"
}
```

### Example - cURL

```bash
curl -X POST https://emailapi.6ray.com/client/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "ABCD1234-5678-90EF-GHIJ-KLMNOPQRSTUV",
    "display_name": "My iPhone 15"
  }'
```

### Example - Swift (iOS)

```swift
struct BootstrapRequest: Codable {
    let device_id: String
    let display_name: String?
}

struct BootstrapResponse: Codable {
    let device_id: String
    let api_key: String
    let username: String
}

func bootstrapDevice() async throws -> BootstrapResponse {
    let url = URL(string: "https://emailapi.6ray.com/client/bootstrap")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    
    let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
    let body = BootstrapRequest(
        device_id: deviceId,
        display_name: UIDevice.current.name
    )
    
    request.httpBody = try JSONEncoder().encode(body)
    
    let (data, response) = try await URLSession.shared.data(for: request)
    
    guard let httpResponse = response as? HTTPURLResponse,
          httpResponse.statusCode == 200 else {
        throw URLError(.badServerResponse)
    }
    
    return try JSONDecoder().decode(BootstrapResponse.self, from: data)
}
```

### Example - JavaScript

```javascript
async function bootstrapDevice() {
  const deviceId = localStorage.getItem('deviceId') || generateDeviceId();
  
  const response = await fetch('https://emailapi.6ray.com/client/bootstrap', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      device_id: deviceId,
      display_name: navigator.userAgent
    })
  });
  
  const data = await response.json();
  
  // Store API key for future requests
  localStorage.setItem('apiKey', data.api_key);
  localStorage.setItem('deviceId', data.device_id);
  
  return data;
}

function generateDeviceId() {
  return 'web-' + Math.random().toString(36).substr(2, 16);
}
```

### Notes

- If the device already exists, returns the existing API key and updates display name
- Device IDs must be at least 16 characters long (configurable)
- API keys are automatically generated and encrypted
- Store the API key securely - it's needed for all subsequent requests

---

## Send Email

Send a single email to one recipient.

### Endpoint

```
POST /send-email
```

**Authentication:** Required (X-API-Key header)

### Request Body

```json
{
  "to_email": "recipient@example.com",
  "subject": "Your Subject Here",
  "message": "Email content in HTML or plain text",
  "from_name": "Sender Name"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `to_email` | String (Email) | **Yes** | Recipient email address |
| `subject` | String | **Yes** | Email subject line |
| `message` | String | **Yes** | Email body (HTML or plain text) |
| `from_name` | String | No | Sender name (defaults to configured sender) |

### Response - Success

```json
{
  "success": true,
  "message": "Email sent successfully",
  "email_id": "msg_12345"
}
```

### Response - Error

```json
{
  "success": false,
  "message": "Error description"
}
```

### Example - cURL

```bash
curl -X POST https://emailapi.6ray.com/send-email \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "to_email": "user@example.com",
    "subject": "Welcome Email",
    "message": "<h1>Welcome!</h1><p>Thank you for signing up.</p>",
    "from_name": "MyApp Team"
  }'
```

### Example - Swift (iOS)

```swift
struct EmailRequest: Codable {
    let to_email: String
    let subject: String
    let message: String
    let from_name: String?
}

struct EmailResponse: Codable {
    let success: Bool
    let message: String
    let email_id: String?
}

func sendEmail(to: String, subject: String, message: String, apiKey: String) async throws -> EmailResponse {
    let url = URL(string: "https://emailapi.6ray.com/send-email")!
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
    
    let body = EmailRequest(
        to_email: to,
        subject: subject,
        message: message,
        from_name: "MyApp"
    )
    
    request.httpBody = try JSONEncoder().encode(body)
    
    let (data, response) = try await URLSession.shared.data(for: request)
    
    guard let httpResponse = response as? HTTPURLResponse,
          (200...299).contains(httpResponse.statusCode) else {
        throw URLError(.badServerResponse)
    }
    
    return try JSONDecoder().decode(EmailResponse.self, from: data)
}
```

### Example - JavaScript

```javascript
async function sendEmail(to, subject, message, apiKey) {
  const response = await fetch('https://emailapi.6ray.com/send-email', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey
    },
    body: JSON.stringify({
      to_email: to,
      subject: subject,
      message: message,
      from_name: 'MyApp'
    })
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || 'Failed to send email');
  }
  
  return await response.json();
}

// Usage
try {
  const result = await sendEmail(
    'user@example.com',
    'Welcome!',
    '<h1>Hello</h1><p>Welcome to our service.</p>',
    localStorage.getItem('apiKey')
  );
  console.log('Email sent:', result);
} catch (error) {
  console.error('Failed to send email:', error);
}
```

### Example - Python

```python
import requests

def send_email(to_email, subject, message, api_key, from_name=None):
    url = "https://emailapi.6ray.com/send-email"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    
    payload = {
        "to_email": to_email,
        "subject": subject,
        "message": message
    }
    
    if from_name:
        payload["from_name"] = from_name
    
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    
    return response.json()

# Usage
result = send_email(
    to_email="user@example.com",
    subject="Welcome Email",
    message="<h1>Welcome!</h1><p>Thank you for joining.</p>",
    api_key="your-api-key-here",
    from_name="MyApp Team"
)
print(result)
```

---

## Send Bulk Email

Send the same email to multiple recipients efficiently. Ideal for newsletters, notifications, or mailing lists.

### Endpoint

```
POST /send-bulk-email
```

**Authentication:** Required (X-API-Key header)

### Request Body

```json
{
  "to_emails": [
    "user1@example.com",
    "user2@example.com",
    "user3@example.com"
  ],
  "subject": "Newsletter - October 2025",
  "message": "<h1>Monthly Update</h1><p>Check out what's new...</p>",
  "from_name": "Newsletter Team"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `to_emails` | Array[String] | **Yes** | List of recipient email addresses |
| `subject` | String | **Yes** | Email subject line |
| `message` | String | **Yes** | Email body (HTML or plain text) |
| `from_name` | String | No | Sender name |

### Response

```json
{
  "total": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {
      "email": "user1@example.com",
      "success": true,
      "message": "Email sent successfully"
    },
    {
      "email": "user2@example.com",
      "success": true,
      "message": "Email sent successfully"
    },
    {
      "email": "user3@example.com",
      "success": true,
      "message": "Email sent successfully"
    }
  ]
}
```

### Example - cURL

```bash
curl -X POST https://emailapi.6ray.com/send-bulk-email \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "to_emails": [
      "user1@example.com",
      "user2@example.com",
      "user3@example.com"
    ],
    "subject": "Important Announcement",
    "message": "<h1>Update</h1><p>Important information...</p>",
    "from_name": "Team"
  }'
```

### Example - JavaScript

```javascript
async function sendBulkEmail(recipients, subject, message, apiKey) {
  const response = await fetch('https://emailapi.6ray.com/send-bulk-email', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey
    },
    body: JSON.stringify({
      to_emails: recipients,
      subject: subject,
      message: message,
      from_name: 'MyApp'
    })
  });
  
  if (!response.ok) {
    throw new Error('Bulk email failed');
  }
  
  return await response.json();
}

// Usage
const recipients = [
  'user1@example.com',
  'user2@example.com',
  'user3@example.com'
];

const result = await sendBulkEmail(
  recipients,
  'Monthly Newsletter',
  '<h1>October Update</h1><p>Latest news...</p>',
  localStorage.getItem('apiKey')
);

console.log(`Sent ${result.successful}/${result.total} emails`);
result.results.forEach(r => {
  console.log(`${r.email}: ${r.success ? '✓' : '✗'} ${r.message}`);
});
```

### Example - Python

```python
import requests

def send_bulk_email(to_emails, subject, message, api_key, from_name=None):
    url = "https://emailapi.6ray.com/send-bulk-email"
    
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    
    payload = {
        "to_emails": to_emails,
        "subject": subject,
        "message": message
    }
    
    if from_name:
        payload["from_name"] = from_name
    
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    
    return response.json()

# Usage
recipients = [
    "user1@example.com",
    "user2@example.com",
    "user3@example.com"
]

result = send_bulk_email(
    to_emails=recipients,
    subject="Newsletter - October 2025",
    message="<h1>Monthly Update</h1><p>Latest news...</p>",
    api_key="your-api-key-here",
    from_name="Newsletter Team"
)

print(f"Sent {result['successful']}/{result['total']} emails")
for r in result['results']:
    status = '✓' if r['success'] else '✗'
    print(f"{status} {r['email']}: {r['message']}")
```

### Notes

- Each email is sent individually with per-recipient status tracking
- Failed emails don't affect successful ones
- Consider rate limits and batch sizes for large mailing lists
- Response includes detailed status for each recipient

---

## Health Check

Verify the service is running and responsive.

### Endpoint

```
GET /health
```

**Authentication:** None required

### Response

```json
{
  "status": "healthy",
  "service": "email-api"
}
```

### Example

```bash
curl https://emailapi.6ray.com/health
```

---

## Configuration Status

Check the current email provider configuration status.

### Endpoint

```
GET /config/status
```

**Authentication:** None required

### Response

```json
{
  "email_provider": "Amazon SES",
  "configured": true,
  "message": "Amazon SES is configured and ready"
}
```

### Example

```bash
curl https://emailapi.6ray.com/config/status
```

---

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Invalid or missing API key |
| 403 | Forbidden - Device disabled or domain blocked |
| 404 | Not Found |
| 422 | Validation Error - Check request format |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Email provider not configured |

### Error Response Format

```json
{
  "detail": "Error description"
}
```

Or for validation errors:

```json
{
  "detail": [
    {
      "loc": ["body", "to_email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

### Common Errors

#### Invalid API Key

```json
{
  "detail": "Invalid or revoked API key"
}
```

**Solution:** Re-bootstrap the device to get a new API key.

#### Domain Blocked

```json
{
  "detail": "Recipient domain is blocked"
}
```

**Solution:** Contact admin to update domain policy.

#### Email Provider Not Configured

```json
{
  "detail": "No AI provider configured. Configure one in /admin/aiconfig"
}
```

**Solution:** Admin needs to configure email provider via admin panel.

### Error Handling Example - JavaScript

```javascript
async function sendEmailSafe(to, subject, message, apiKey) {
  try {
    const response = await fetch('https://emailapi.6ray.com/send-email', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey
      },
      body: JSON.stringify({ to_email: to, subject, message })
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      if (response.status === 401) {
        // Re-bootstrap device
        console.log('API key invalid, re-bootstrapping...');
        const bootstrap = await bootstrapDevice();
        return sendEmailSafe(to, subject, message, bootstrap.api_key);
      } else if (response.status === 403) {
        throw new Error('Domain blocked or device disabled');
      } else if (response.status === 422) {
        throw new Error('Invalid email format: ' + JSON.stringify(error.detail));
      }
      
      throw new Error(error.detail || 'Unknown error');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Email send error:', error);
    throw error;
  }
}
```

---

## Admin Endpoints

Admin endpoints require HTTP Basic authentication with username `admin` and password configured in `PANEL_PASSWORD`.

### Admin Panel

**URL:** `https://emailapi.6ray.com/admin/config`  
**Default Password:** `771008`

**Features:**
- Switch between Gmail SMTP and Amazon SES
- Configure email provider credentials
- Test connection and send test emails
- Manage API keys
- Configure domain policies (allow/block lists)
- Create seed user keys

### Admin API Endpoints

#### Create API Key

```
POST /admin/keys/create
Content-Type: application/json
Authorization: Bearer {ADMIN_TOKEN}

{
  "username": "test-user"
}
```

Response:
```json
{
  "api_key": "generated-key-here"
}
```

#### Revoke API Key

```
POST /admin/keys/revoke/{key_id}
Authorization: Bearer {ADMIN_TOKEN}
```

Response:
```json
{
  "revoked": true,
  "key_id": "key-id-here"
}
```

#### List All Keys

```
GET /admin/keys
Authorization: Bearer {ADMIN_TOKEN}
```

Response:
```json
{
  "keys": [
    {
      "key_id": "abc123",
      "username": "ios_device12345",
      "is_seed": false,
      "created_at": "2025-10-31T10:00:00",
      "revoked_at": null
    }
  ]
}
```

---

## Domain Policies

Administrators can configure domain-based recipient filtering:

### Allow List (Whitelist)

If configured, **only** emails to these domains are allowed:
```
ALLOW_DOMAINS=example.com,mycompany.com
```

### Block List (Blacklist)

Prevent emails to these domains:
```
BLOCK_DOMAINS=spam.com,blocked.net
```

### Default Behavior

- If `ALLOW_DOMAINS` is empty: All domains allowed (except blocked ones)
- If `ALLOW_DOMAINS` is set: Only listed domains allowed
- `BLOCK_DOMAINS` always takes precedence

---

## Rate Limits

**Best Practices:**
- Implement client-side rate limiting
- Use bulk-send for multiple recipients
- Cache API keys to avoid repeated bootstrapping
- Handle 429 responses with exponential backoff

---

## Email HTML Tips

### Best Practices

1. **Use inline CSS** - Email clients have limited CSS support
2. **Tables for layout** - Most reliable across email clients
3. **Test across clients** - Gmail, Outlook, Apple Mail render differently
4. **Include plain text alternative** - For accessibility

### Example HTML Email

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden;">
          <tr>
            <td style="padding: 40px; text-align: center;">
              <h1 style="color: #333333; margin: 0 0 20px 0;">Welcome!</h1>
              <p style="color: #666666; font-size: 16px; line-height: 1.5;">
                Thank you for signing up. We're excited to have you!
              </p>
              <a href="https://example.com" 
                 style="display: inline-block; margin-top: 20px; padding: 12px 30px; 
                        background-color: #007bff; color: #ffffff; text-decoration: none; 
                        border-radius: 4px;">Get Started</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

---

## Testing

### Quick Test with cURL

```bash
# 1. Bootstrap device
curl -X POST https://emailapi.6ray.com/client/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"device_id":"test-device-12345678","display_name":"Test Device"}'

# Save the api_key from response, then:

# 2. Send test email
curl -X POST https://emailapi.6ray.com/send-email \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -d '{
    "to_email":"your-email@example.com",
    "subject":"Test Email",
    "message":"<h1>Test</h1><p>This is a test email.</p>"
  }'
```

### Test Checklist

- ✅ Bootstrap returns valid API key
- ✅ Health check returns healthy status
- ✅ Config status shows provider configured
- ✅ Send email succeeds with valid API key
- ✅ Send email fails with invalid API key (401)
- ✅ Invalid email format returns validation error (422)
- ✅ Bulk send handles multiple recipients
- ✅ Bulk send reports per-recipient status

---

## Support

**Admin Panel:** `https://emailapi.6ray.com/admin/config` (password: `771008`)

**API Documentation:** `https://emailapi.6ray.com/docs` (Interactive Swagger UI)

**Configuration:**
- Email provider: Admin panel
- Domain policies: Admin panel
- API key management: Admin panel or API endpoints

**For issues:**
- Check service health: `GET /health`
- Check provider status: `GET /config/status`
- Verify API key validity: Try sending a test email
- Contact administrator for domain policy or provider configuration issues

---

## Security Best Practices

### Client-Side

1. **Store API keys securely**
   - iOS: Use Keychain
   - Android: Use EncryptedSharedPreferences
   - Web: Use secure httpOnly cookies or IndexedDB with encryption

2. **Don't hardcode credentials**
   - Use environment variables or secure configuration

3. **Validate input before sending**
   - Check email format client-side
   - Sanitize HTML content

### Server-Side (Admin)

1. **Rotate admin tokens regularly**
2. **Use strong passwords** for admin panel
3. **Enable HTTPS** (already configured)
4. **Monitor API usage** for abuse
5. **Configure domain policies** to limit recipients

---

## Architecture

### Email Provider Abstraction

The service uses a provider pattern for easy switching between email services:

```
EmailService (Facade)
    ↓
EmailProviderFactory
    ↓
    ├─ GmailProvider (SMTP)
    └─ SESProvider (AWS SDK)
```

**Benefits:**
- Switch providers without code changes
- Add new providers easily
- Provider-specific configuration isolation
- Independent testing per provider

---

## Migration Guide

### From Direct SMTP to API

**Before:**
```python
import smtplib
# Direct SMTP connection with credentials
```

**After:**
```python
import requests
# Simple API call with API key
```

**Steps:**
1. Bootstrap device to get API key
2. Replace SMTP code with API calls
3. Store API key securely
4. Update error handling for HTTP responses

### From Other Email Services

Replace your email service calls with Email API endpoints:

| Old Service | New Endpoint |
|-------------|--------------|
| SendGrid | `/send-email` |
| Mailgun | `/send-email` |
| Direct SMTP | `/send-email` |
| Bulk services | `/send-bulk-email` |

---

## License

This service is provided as-is. Contact your organization for usage policies and terms.
