from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Annotated
import sqlite3
import os
import string
from datetime import datetime
from contextlib import asynccontextmanager
from email_service import EmailService
from config import Config
from api_keys import (
    init_db,
    verify_key,
    create_key,
    revoke_key,
    list_keys,
    delete_seed_user,
    delete_all_seed_users,
    register_device,
    get_device,
    touch_device,
)

email_service = EmailService()
config = Config()

class EmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    message: str
    from_name: Optional[str] = None

class EmailResponse(BaseModel):
    success: bool
    message: str
    email_id: Optional[str] = None


class BootstrapRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    device_id: Annotated[str, Field(min_length=8, max_length=128)]
    display_name: Optional[str] = None


class BootstrapResponse(BaseModel):
    device_id: str
    api_key: str
    username: str


DB_PATH = os.getenv("API_KEYS_DB", "./api_keys.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")  # for managing keys
REG_TOKEN = os.getenv("REG_TOKEN")  # for client self-registration
DEVICE_USERNAME_PREFIX = os.getenv("DEVICE_USERNAME_PREFIX", "ios")
MIN_DEVICE_ID_LENGTH = int(os.getenv("DEVICE_ID_MIN_LENGTH", "16"))
ALLOW_DOMAINS = [d.strip().lower() for d in os.getenv("ALLOW_DOMAINS", "").split(",") if d.strip()]
BLOCK_DOMAINS = [d.strip().lower() for d in os.getenv("BLOCK_DOMAINS", "").split(",") if d.strip()]
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "771008")
ENV_FILE_PATH = os.getenv("ENV_FILE_PATH", ".env")

basic_security = HTTPBasic()


def _normalize_display_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    cleaned = name.strip()
    if not cleaned:
        return None
    return cleaned[:120]


def _generate_device_username(device_id: str) -> str:
    suffix = device_id.replace("-", "").lower()
    if len(suffix) < 6:
        suffix = suffix.ljust(6, "0")
    suffix = suffix[:12]
    return f"{DEVICE_USERNAME_PREFIX}-{suffix}"


def _validate_device_id(raw_id: str) -> str:
    device_id = raw_id.strip()
    if len(device_id) < MIN_DEVICE_ID_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"device_id must be at least {MIN_DEVICE_ID_LENGTH} characters",
        )
    allowed_chars = set(string.ascii_letters + string.digits + "-_.:@")
    if any(ch not in allowed_chars for ch in device_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="device_id contains invalid characters")
    if len(device_id) > 128:
        device_id = device_id[:128]
    return device_id

async def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    """Require a valid per-user client key in the form key_id.secret"""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    username = verify_key(DB_PATH, x_api_key)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return username

def require_admin(x_admin_token: Optional[str] = Header(default=None)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")
    return True

def _extract_domain(email: str) -> str:
    try:
        return email.split("@", 1)[1].lower()
    except Exception:
        return ""

def _domain_matches(domain: str, pattern: str) -> bool:
    # exact or suffix match (pattern may be like '6ray.com' or '.6ray.com')
    pat = pattern.lstrip('.')
    return domain == pat or domain.endswith('.' + pat)

def _enforce_recipient_policy(to_email: str):
    dom = _extract_domain(to_email)
    if not dom:
        raise HTTPException(status_code=422, detail="Invalid recipient email domain")
    # Block list first
    for pat in BLOCK_DOMAINS:
        if _domain_matches(dom, pat):
            raise HTTPException(status_code=403, detail=f"Recipient domain '{dom}' is blocked")
    # Allow list if present
    if ALLOW_DOMAINS:
        for pat in ALLOW_DOMAINS:
            if _domain_matches(dom, pat):
                break
        else:
            raise HTTPException(status_code=403, detail=f"Recipient domain '{dom}' not allowed")

def _load_env_map() -> dict:
    data = {}
    if os.path.exists(ENV_FILE_PATH):
        with open(ENV_FILE_PATH, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                data[k.strip()] = v.strip()
    return data

def _save_env_map(values: dict):
    # Merge with existing
    current = _load_env_map()
    current.update(values)
    lines = ["# Email API configuration\n"]
    for k, v in current.items():
        lines.append(f"{k}={v}\n")
    tmp = ENV_FILE_PATH + ".tmp"
    with open(tmp, 'w') as f:
        f.writelines(lines)
    os.replace(tmp, ENV_FILE_PATH)
    try:
        os.chmod(ENV_FILE_PATH, 0o600)
    except Exception:
        pass

def _reload_runtime_from_env():
    global ADMIN_TOKEN, ALLOW_DOMAINS, BLOCK_DOMAINS
    # Gmail creds
    config.gmail_user = os.getenv('GMAIL_USER') or _load_env_map().get('GMAIL_USER')
    config.gmail_app_password = os.getenv('GMAIL_APP_PASSWORD') or _load_env_map().get('GMAIL_APP_PASSWORD')
    email_service.gmail_user = config.gmail_user
    email_service.gmail_app_password = config.gmail_app_password
    # Policies
    ADMIN_TOKEN = _load_env_map().get('ADMIN_TOKEN', ADMIN_TOKEN)
    ALLOW_DOMAINS = [d.strip().lower() for d in (_load_env_map().get('ALLOW_DOMAINS', '')).split(',') if d.strip()]
    BLOCK_DOMAINS = [d.strip().lower() for d in (_load_env_map().get('BLOCK_DOMAINS', '')).split(',') if d.strip()]

def _panel_auth(credentials: HTTPBasicCredentials = Depends(basic_security)):
    # Accept any username, check password matches configured panel password
    if credentials.password != PANEL_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized (panel)")
    return True

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize email service on startup"""
    # initialize API keys DB
    init_db(DB_PATH)
    await email_service.initialize()
    yield

app = FastAPI(title="Email API Service", version="1.0.0", lifespan=lifespan)


@app.post("/client/bootstrap", response_model=BootstrapResponse)
async def client_bootstrap(payload: BootstrapRequest):
    device_id = _validate_device_id(payload.device_id)
    display_name = _normalize_display_name(payload.display_name)

    existing = get_device(DB_PATH, device_id)
    if existing:
        if existing.get("disabled"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device is disabled")
        touch_device(DB_PATH, device_id, display_name=display_name)
        return BootstrapResponse(
            device_id=device_id,
            api_key=existing["api_key"],
            username=existing["username"],
        )

    username = _generate_device_username(device_id)
    api_key_plain = create_key(DB_PATH, username)
    key_id, _ = api_key_plain.split(".", 1)

    try:
        register_device(
            DB_PATH,
            device_id=device_id,
            username=username,
            key_id=key_id,
            api_key_plain=api_key_plain,
            display_name=display_name,
        )
    except sqlite3.IntegrityError:
        existing = get_device(DB_PATH, device_id)
        if not existing:
            raise HTTPException(status_code=500, detail="Failed to provision device")
        if existing.get("disabled"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device is disabled")
        touch_device(DB_PATH, device_id, display_name=display_name)
        return BootstrapResponse(
            device_id=device_id,
            api_key=existing["api_key"],
            username=existing["username"],
        )

    return BootstrapResponse(device_id=device_id, api_key=api_key_plain, username=username)

@app.post("/send-email", response_model=EmailResponse, dependencies=[Depends(require_api_key)])
async def send_email(email_request: EmailRequest, background_tasks: BackgroundTasks, username: str = Depends(require_api_key)):
    """
    Send an email using Gmail SMTP
    """
    try:
        # Enforce allow/deny domain policy
        _enforce_recipient_policy(email_request.to_email)
        # Add email sending to background tasks for better performance
        background_tasks.add_task(
            email_service.send_email,
            email_request.to_email,
            email_request.subject,
            email_request.message,
            email_request.from_name
        )

        return EmailResponse(
            success=True,
            message=f"Email queued for sending (by {username})",
            email_id=f"{email_request.to_email}_{hash(email_request.subject)}"
        )
    except HTTPException:
        # pass through expected HTTP errors like 403/422
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue email: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "email-api"}

@app.get("/config/status")
async def config_status():
    """Check email provider configuration status"""
    provider_name = email_service.get_provider_name()
    is_configured = email_service.provider.is_configured()
    return {
        "email_provider": provider_name,
        "configured": is_configured,
        "message": f"{provider_name} is configured and ready" if is_configured else f"{provider_name} configuration needed"
    }

# --- Admin Config Panel (password protected) ---

def _render_panel(message: str = "") -> str:
    # Load current configuration
    env_vars = _load_env_map()
    email_provider = env_vars.get('EMAIL_PROVIDER', 'gmail')
    gmail_user = env_vars.get('GMAIL_USER', '')
    aws_region = env_vars.get('AWS_REGION', 'us-east-1')
    aws_access_key = env_vars.get('AWS_ACCESS_KEY_ID', '')
    ses_from_email = env_vars.get('SES_FROM_EMAIL', '')
    ses_config_set = env_vars.get('SES_CONFIGURATION_SET', '')
    
    allow = ",".join(ALLOW_DOMAINS)
    block = ",".join(BLOCK_DOMAINS)
    keys = list_keys(DB_PATH)
    
    # Provider selection dropdown
    provider_options = f"""
        <option value="gmail" {'selected' if email_provider == 'gmail' else ''}>Gmail SMTP</option>
        <option value="ses" {'selected' if email_provider == 'ses' else ''}>Amazon SES</option>
    """
    
    html = f"""
    <html><head><title>Email API Config</title>
    <style>
    body{{font-family:sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}}
    form{{border:1px solid #ddd;padding:1rem;margin-bottom:1rem;border-radius:8px}}
    label{{display:block;margin:.5rem 0 .25rem;font-weight:bold}}
    input[type=text],input[type=password],textarea,select{{width:100%;padding:.5rem;box-sizing:border-box}}
    button{{margin-top:.75rem;padding:.5rem 1rem;cursor:pointer}}
    .provider-section{{display:none}}
    .provider-section.active{{display:block}}
    .help-text{{font-size:0.9em;color:#666;margin-top:0.25rem}}
    </style>
    <script>
    function toggleProvider() {{
        var provider = document.getElementById('email_provider').value;
        document.getElementById('gmail-section').classList.remove('active');
        document.getElementById('ses-section').classList.remove('active');
        if (provider === 'gmail') {{
            document.getElementById('gmail-section').classList.add('active');
        }} else if (provider === 'ses') {{
            document.getElementById('ses-section').classList.add('active');
        }}
    }}
    window.onload = function() {{ toggleProvider(); }}
    </script>
    </head><body>
    <h1>Email API Configuration</h1>
    {f'<p style=\"color:green;font-weight:bold\">{message}</p>' if message else ''}
    
    <h2>Email Provider Selection</h2>
    <form method="post" action="/admin/config/provider">
      <label>Email Provider</label>
      <select name="email_provider" id="email_provider" onchange="toggleProvider()">
        {provider_options}
      </select>
      <div class="help-text">Choose between Gmail SMTP or Amazon SES for sending emails</div>
      <button type="submit">Save Provider Selection</button>
    </form>
    
    <div id="gmail-section" class="provider-section">
      <h2>Gmail SMTP Configuration</h2>
      <form method="post" action="/admin/config/gmail">
        <label>Gmail Address</label>
        <input name="gmail_user" type="text" value="{gmail_user}" placeholder="your-email@gmail.com" />
        <div class="help-text">Your Gmail address to send emails from</div>
        
        <label>App Password (16 chars, no spaces)</label>
        <input name="gmail_app_password" type="password" value="" placeholder="••••••••••••••••" />
        <div class="help-text">Generate at: <a href="https://myaccount.google.com/apppasswords" target="_blank">Google App Passwords</a></div>
        <button type="submit">Save Gmail Settings</button>
      </form>
    </div>
    
    <div id="ses-section" class="provider-section">
      <h2>Amazon SES Configuration</h2>
      <form method="post" action="/admin/config/ses">
        <label>AWS Region</label>
        <input name="aws_region" type="text" value="{aws_region}" placeholder="us-east-2" />
        <div class="help-text">AWS region where your SES is configured (e.g., us-east-2 for Ohio, us-east-1 for Virginia)</div>
        
        <label>AWS Access Key ID</label>
        <input name="aws_access_key_id" type="text" value="{aws_access_key}" placeholder="AKIAIOSFODNN7EXAMPLE" />
        <div class="help-text">IAM user access key with ses:SendEmail permission</div>
        
        <label>AWS Secret Access Key</label>
        <input name="aws_secret_access_key" type="password" value="" placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" />
        <div class="help-text">IAM user secret key (will not be displayed after saving)</div>
        
        <label>SES From Email</label>
        <input name="ses_from_email" type="text" value="{ses_from_email}" placeholder="noreply@yourdomain.com" />
        <div class="help-text">Verified sender email address in SES</div>
        
        <label>SES Configuration Set (Optional)</label>
        <input name="ses_configuration_set" type="text" value="{ses_config_set}" placeholder="my-config-set" />
        <div class="help-text">Optional: SES configuration set for tracking</div>
        
        <button type="submit">Save Amazon SES Settings</button>
      </form>
    </div>

    <h2>Test Email Configuration</h2>
    <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
      <form method="post" action="/admin/config/test-connection" style="margin-bottom: 15px;">
        <div class="help-text">Test if your email provider credentials are valid and the service is reachable</div>
        <button type="submit" style="background: #0066cc;">Test Connection</button>
      </form>
      
      <form method="post" action="/admin/config/test-email">
        <label>Test Email Recipient</label>
        <input name="test_email" type="email" placeholder="your@email.com" required />
        <div class="help-text">Send a test email to verify end-to-end email delivery</div>
        <button type="submit" style="background: #28a745;">Send Test Email</button>
      </form>
    </div>

    <h2>Recipient Domain Policy</h2>
    <form method="post" action="/admin/config/domains">
      <label>Allow Domains (comma-separated, leave empty to allow all)</label>
      <input name="allow_domains" type="text" value="{allow}" />
      <label>Block Domains (comma-separated)</label>
      <input name="block_domains" type="text" value="{block}" />
      <button type="submit">Save Domain Policy</button>
    </form>

        <h2>Create iOS Client API Key</h2>
    <form method="post" action="/admin/config/create-key">
      <label>Username/Device ID</label>
      <input name="username" type="text" placeholder="ios-client-1" />
      <button type="submit">Create Key</button>
    </form>

        <h2>Seed Users</h2>
        <form method="post" action="/admin/config/create-seed">
            <label>Seed Username</label>
            <input name="username" type="text" placeholder="seed-user-1" />
            <button type="submit">Create Seed User Key</button>
        </form>
        <form method="post" action="/admin/config/delete-seed">
            <label>Delete Seed Username</label>
            <input name="username" type="text" placeholder="seed-user-1" />
            <button type="submit">Delete Seed User Keys</button>
        </form>
        <form method="post" action="/admin/config/delete-all-seeds">
            <p>Delete all seed user keys (irreversible).</p>
            <button type="submit" onclick="return confirm('Delete ALL seed user keys?')">Delete All Seed Users</button>
        </form>

        <h2>Existing Keys</h2>
        <div style="overflow:auto;max-height:300px;border:1px solid #ddd;padding:.5rem;border-radius:6px">
            <table width="100%" cellpadding="4" cellspacing="0">
                <tr><th align="left">Key ID</th><th align="left">Username</th><th align="left">Seed</th><th align="left">Created</th><th align="left">Revoked</th></tr>
                {''.join(f"<tr><td>{k['key_id']}</td><td>{k['username']}</td><td>{'yes' if k.get('is_seed') else ''}</td><td>{k['created_at']}</td><td>{k['revoked_at'] or ''}</td></tr>" for k in keys)}
            </table>
        </div>

    <h2>Admin Token</h2>
    <form method="post" action="/admin/config/rotate-admin">
      <p>Rotate ADMIN_TOKEN used for admin API endpoints.</p>
      <button type="submit">Rotate Admin Token</button>
    </form>

    </body></html>
    """
    return html

@app.get("/admin/config", response_class=HTMLResponse)
async def admin_config_panel(_: bool = Depends(_panel_auth)):
    return HTMLResponse(content=_render_panel())

@app.post("/admin/config/gmail")
async def admin_config_gmail(
    gmail_user: str = Form(...),
    gmail_app_password: str = Form(""),
    _: bool = Depends(_panel_auth),
):
    updates = {"GMAIL_USER": gmail_user.strip()}
    if gmail_app_password.strip():
        updates["GMAIL_APP_PASSWORD"] = gmail_app_password.strip().replace(" ", "")
    _save_env_map(updates)
    _reload_runtime_from_env()
    return HTMLResponse(content=_render_panel("Gmail settings saved. Restart service to apply changes."))

@app.post("/admin/config/provider")
async def admin_config_provider(
    email_provider: str = Form(...),
    _: bool = Depends(_panel_auth),
):
    provider = email_provider.strip().lower()
    if provider not in ['gmail', 'ses']:
        return HTMLResponse(content=_render_panel(f"Invalid provider: {provider}"))
    _save_env_map({"EMAIL_PROVIDER": provider})
    _reload_runtime_from_env()
    return HTMLResponse(content=_render_panel(f"Email provider set to {provider.upper()}. Restart service to apply changes."))

@app.post("/admin/config/ses")
async def admin_config_ses(
    aws_region: str = Form(...),
    aws_access_key_id: str = Form(...),
    aws_secret_access_key: str = Form(""),
    ses_from_email: str = Form(...),
    ses_configuration_set: str = Form(""),
    _: bool = Depends(_panel_auth),
):
    updates = {
        "AWS_REGION": aws_region.strip(),
        "AWS_ACCESS_KEY_ID": aws_access_key_id.strip(),
        "SES_FROM_EMAIL": ses_from_email.strip(),
    }
    if aws_secret_access_key.strip():
        updates["AWS_SECRET_ACCESS_KEY"] = aws_secret_access_key.strip()
    if ses_configuration_set.strip():
        updates["SES_CONFIGURATION_SET"] = ses_configuration_set.strip()
    _save_env_map(updates)
    _reload_runtime_from_env()
    return HTMLResponse(content=_render_panel("Amazon SES settings saved. Restart service to apply changes."))

@app.post("/admin/config/test-email")
async def admin_config_test_email(
    test_email: str = Form(...),
    _: bool = Depends(_panel_auth),
):
    """Send a test email to verify email provider configuration"""
    provider_name = email_service.get_provider_name()
    
    # First check if provider is configured
    if not email_service.provider.is_configured():
        return HTMLResponse(content=_render_panel(
            f"❌ {provider_name} is not configured. Please configure your email provider settings first."
        ))
    
    try:
        # Try to send test email
        success = await email_service.send_email(
            to_email=test_email.strip(),
            subject="Email API Test - Configuration Successful",
            message=f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>✅ Email Configuration Test Successful</h2>
                <p>This is a test email from your Email API service.</p>
                <hr>
                <p><strong>Provider:</strong> {provider_name}</p>
                <p><strong>Test Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <p><strong>Server:</strong> emailapi.6ray.com</p>
                <hr>
                <p style="color: #666; font-size: 12px;">
                    If you received this email, your email provider is configured correctly and ready to send emails.
                </p>
            </body>
            </html>
            """,
            from_name="Email API Test"
        )
        
        if success:
            return HTMLResponse(content=_render_panel(
                f"✅ Test email sent successfully to {test_email} using {provider_name}. Check your inbox (and spam folder)!"
            ))
        else:
            return HTMLResponse(content=_render_panel(
                f"❌ Failed to send test email using {provider_name}. The send operation returned False. Check server logs for details."
            ))
    except Exception as e:
        error_details = str(e)
        return HTMLResponse(content=_render_panel(
            f"❌ Error sending test email via {provider_name}: {error_details}"
        ))

@app.post("/admin/config/test-connection")
async def admin_config_test_connection(
    _: bool = Depends(_panel_auth),
):
    """Test connection to email provider without sending email"""
    provider_name = email_service.get_provider_name()
    
    # Check if configured
    if not email_service.provider.is_configured():
        return HTMLResponse(content=_render_panel(
            f"❌ {provider_name} is not configured. Please set up your credentials first."
        ))
    
    try:
        # Test connection
        connection_ok = await email_service.provider.test_connection()
        
        if connection_ok:
            return HTMLResponse(content=_render_panel(
                f"✅ Connection successful! {provider_name} is properly configured and reachable."
            ))
        else:
            return HTMLResponse(content=_render_panel(
                f"❌ Connection test failed for {provider_name}. Check your credentials and network connectivity."
            ))
    except Exception as e:
        error_details = str(e)
        return HTMLResponse(content=_render_panel(
            f"❌ Connection error with {provider_name}: {error_details}"
        ))

@app.post("/admin/config/domains")
async def admin_config_domains(
    allow_domains: str = Form(""),
    block_domains: str = Form(""),
    _: bool = Depends(_panel_auth),
):
    updates = {
        "ALLOW_DOMAINS": ",".join([d.strip() for d in allow_domains.split(",") if d.strip()]),
        "BLOCK_DOMAINS": ",".join([d.strip() for d in block_domains.split(",") if d.strip()]),
    }
    _save_env_map(updates)
    _reload_runtime_from_env()
    return HTMLResponse(content=_render_panel("Domain policy saved."))

@app.post("/admin/config/create-key")
async def admin_config_create_key(username: str = Form(...), _: bool = Depends(_panel_auth)):
    key = create_key(DB_PATH, username.strip())
    msg = f"Created key for {username}: <code>{key}</code>"
    return HTMLResponse(content=_render_panel(msg))

@app.post("/admin/config/rotate-admin")
async def admin_config_rotate_admin(_: bool = Depends(_panel_auth)):
    import secrets
    new_tok = secrets.token_hex(32)
    _save_env_map({"ADMIN_TOKEN": new_tok})
    _reload_runtime_from_env()
    return HTMLResponse(content=_render_panel("Admin token rotated."))

@app.post("/admin/config/create-seed")
async def admin_config_create_seed(username: str = Form(...), _: bool = Depends(_panel_auth)):
    key = create_key(DB_PATH, username.strip(), is_seed=True)
    msg = f"Created SEED key for {username}: <code>{key}</code>"
    return HTMLResponse(content=_render_panel(msg))

@app.post("/admin/config/delete-seed")
async def admin_config_delete_seed(username: str = Form(...), _: bool = Depends(_panel_auth)):
    deleted = delete_seed_user(DB_PATH, username.strip())
    msg = f"Deleted {deleted} keys for seed user {username}."
    return HTMLResponse(content=_render_panel(msg))

@app.post("/admin/config/delete-all-seeds")
async def admin_config_delete_all_seeds(_: bool = Depends(_panel_auth)):
    deleted = delete_all_seed_users(DB_PATH)
    msg = f"Deleted ALL seed user keys: {deleted} removed."
    return HTMLResponse(content=_render_panel(msg))
# --- Admin endpoints ---
class CreateKeyRequest(BaseModel):
    username: str

@app.post("/admin/keys/create")
async def admin_create_key(body: CreateKeyRequest, ok: bool = Depends(require_admin)):
    key = create_key(DB_PATH, body.username)
    return {"api_key": key}

@app.post("/admin/keys/revoke/{key_id}")
async def admin_revoke_key(key_id: str, ok: bool = Depends(require_admin)):
    success = revoke_key(DB_PATH, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found or already revoked")
    return {"revoked": True, "key_id": key_id}

@app.get("/admin/keys")
async def admin_list_keys(ok: bool = Depends(require_admin)):
    return {"keys": list_keys(DB_PATH)}

# --- Client self-registration (optional) ---
class RegisterKeyRequest(BaseModel):
    username: str

@app.post("/register/key")
async def register_key(body: RegisterKeyRequest, x_registration_token: Optional[str] = Header(default=None)):
    if not REG_TOKEN or x_registration_token != REG_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid registration token")
    key = create_key(DB_PATH, body.username.strip())
    return {"api_key": key}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)