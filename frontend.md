# Frontend Integration Guide

This document explains how iOS (or other client) apps interact with the Email API service hosted at `https://emailapi.6ray.com`. It covers provisioning client credentials, sending email requests, and verifying the deployment from a Mac without pytest.

## API surface

| Endpoint | Method | Purpose | Auth |
| --- | --- | --- | --- |
| `/health` | GET | Basic availability probe. | None |
| `/config/status` | GET | Confirms Gmail credentials are present. | None |
| `/client/bootstrap` | POST | Issues or re-issues a device-scoped API key. | None |
| `/send-email` | POST | Queues an outbound email through Gmail SMTP. | `X-API-Key` header (`key_id.secret`)

The base URL for production is `https://emailapi.6ray.com`. For local simulators you can point to `http://localhost:8002`.

## Bootstrapping a device key

1. **Pick a stable device identifier.** Use the iOS device UUID or another stable string (minimum 16 characters). Avoid PII.
2. **Call `/client/bootstrap`.** The route is idempotent—repeat calls with the same `device_id` return the same key unless the device has been disabled.

```bash
curl -s -X POST https://emailapi.6ray.com/client/bootstrap \
     -H "Content-Type: application/json" \
     -d '{"device_id":"ios-device-uuid-1234","display_name":"QA iPhone"}' \
  | python -m json.tool
```

Successful response:

```json
{
  "device_id": "ios-device-uuid-1234",
  "username": "ios-qaiphone12",
  "api_key": "<key_id>.<secret>"
}
```

Store the `api_key` securely (Keychain for iOS) and reuse it for all subsequent `/send-email` calls. If the API responds with HTTP 403 the device has been administratively disabled; show an appropriate error to the user and route them to support.

> Backend prerequisite: ensure either `DEVICE_KEY_SECRET` (recommended) or `ADMIN_TOKEN` is present in `/opt/emailapi/.env` so the server can encrypt keys at rest.

## Sending an email

1. Load the API key from secure storage.
2. Call `/send-email` with JSON payload:

```http
POST /send-email
Content-Type: application/json
X-API-Key: <key_id.secret>

{
  "to_email": "recipient@example.com",
  "subject": "Your Subject",
  "message": "Body text or HTML",
  "from_name": "Optional Display Name"
}
```

Expected success response:

```json
{
  "success": true,
  "message": "Email queued for sending (by ios-sampledevice)",
  "email_id": "recipient@example.com_-123456789"
}
```

A 401 response indicates an invalid or missing key. A 403 indicates the recipient domain is blocked by policy.

### Swift helper example

```swift
struct EmailRequest: Codable {
    let toEmail: String
    let subject: String
    let message: String
    let fromName: String?
}

enum EmailAPIError: Error {
    case badResponse
    case missingAPIKey
}

enum EmailAPI {
    static let baseURL = URL(string: "https://emailapi.6ray.com")!

    static func sendEmail(request: EmailRequest, apiKey: String?) async throws -> Bool {
        guard let apiKey else { throw EmailAPIError.missingAPIKey }
        var urlRequest = URLRequest(url: baseURL.appendingPathComponent("/send-email"))
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        urlRequest.httpBody = try JSONEncoder().encode(request)

        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw EmailAPIError.badResponse
        }
        return try JSONDecoder().decode(EmailResponse.self, from: data).success
    }
}

struct EmailResponse: Codable {
    let success: Bool
    let message: String
    let emailId: String?
}
```

## Verifying the deployment from macOS

The repository ships with `ios_smoke_test.py`, a lightweight end-to-end test that does not require pytest.

```bash
# 1) Bootstrap a key (optional — you can also supply an existing key)
curl -s -X POST https://emailapi.6ray.com/client/bootstrap \
     -H "Content-Type: application/json" \
     -d '{"device_id":"mac-smoke-000001","display_name":"Mac Smoke"}' \
  | python -m json.tool

# 2) Run the smoke test
python ios_smoke_test.py \
  --base-url https://emailapi.6ray.com \
  --api-key <key_id.secret-from-bootstrap> \
  --to-email dd@6ray.com \
  --from-name "Mac Smoke" \
  --subject "Bootstrap smoke" \
  --message "Automated smoke test from mac"
```

The script checks `/health`, `/config/status`, and enqueues a real email. Add `--bootstrap` if you prefer the script to mint (and cache) the API key automatically.

Environment variable shortcuts:

- `EMAIL_API_BASE_URL`
- `EMAIL_API_KEY`
- `EMAIL_API_TEST_RECIPIENT`
- `EMAIL_API_DISPLAY_NAME`

These are read automatically by `ios_smoke_test.py`, so you can define them in your shell profile and run the script with no flags.

## Operational tips for frontend engineers

- Coordinate with backend whenever you need to rotate or revoke a device key—revocation happens in the admin panel or via `/admin/keys/revoke/<key_id>`.
- Handle 401/403 responses by prompting the user to rebootstrap or contact support.
- Cache the bootstrap response locally so repeated launches do not re-hit the provisioning endpoint.
- Log the `email_id` returned by `/send-email`; it helps correlate support tickets with backend logs.
- When testing against staging/local, override the base URL and optionally disable certificate validation if using self-signed certs.
