from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Annotated
import sqlite3
import os
import string
from contextlib import asynccontextmanager
from email_service import EmailService
from config import Config
from mail_config_store import load_mail_config, save_mail_config
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
    
    # Load configuration from three sources in order of precedence:
    # 1. Environment variables (highest priority)
    # 2. .env file
    # 3. mail_config.json (lowest priority)
    env_map = _load_env_map()
    mail_config = load_mail_config()
    
    # Helper to get value with fallback priority: env var -> .env file -> mail_config.json
    def get_config_value(key: str, default=None):
        return os.getenv(key) or env_map.get(key) or mail_config.get(key.lower()) or default
    
    # Mail provider configuration
    config.mail_provider = get_config_value('MAIL_PROVIDER', 'gmail')
    config.mail_from = get_config_value('MAIL_FROM')
    
    # Gmail credentials
    config.gmail_user = get_config_value('GMAIL_USER')
    config.gmail_app_password = get_config_value('GMAIL_APP_PASSWORD')
    
    # AWS SES credentials
    config.aws_access_key_id = get_config_value('AWS_ACCESS_KEY_ID')
    config.aws_secret_access_key = get_config_value('AWS_SECRET_ACCESS_KEY')
    config.aws_region = get_config_value('AWS_REGION')
    
    # Update email_service fields
    email_service.mail_provider = config.mail_provider
    email_service.mail_from = config.mail_from
    email_service.gmail_user = config.gmail_user
    email_service.gmail_app_password = config.gmail_app_password
    email_service.aws_access_key_id = config.aws_access_key_id
    email_service.aws_secret_access_key = config.aws_secret_access_key
    email_service.aws_region = config.aws_region
    
    # Policies
    ADMIN_TOKEN = get_config_value('ADMIN_TOKEN', ADMIN_TOKEN)
    ALLOW_DOMAINS = [d.strip().lower() for d in (get_config_value('ALLOW_DOMAINS', '')).split(',') if d.strip()]
    BLOCK_DOMAINS = [d.strip().lower() for d in (get_config_value('BLOCK_DOMAINS', '')).split(',') if d.strip()]

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
    """Check if Gmail configuration is set up"""
    is_configured = config.is_gmail_configured()
    return {
        "gmail_configured": is_configured,
        "message": "Gmail is configured and ready" if is_configured else "Gmail configuration needed"
    }

# --- Admin Config Panel (password protected) ---

def _render_panel(message: str = "") -> str:
    gmail_user = config.gmail_user or ""
    mail_provider = config.mail_provider or "gmail"
    mail_from = config.mail_from or ""
    aws_region = config.aws_region or ""
    allow = ",".join(ALLOW_DOMAINS)
    block = ",".join(BLOCK_DOMAINS)
    keys = list_keys(DB_PATH)
    html = f"""
    <html><head><title>Email API Config</title>
    <style>body{{font-family:sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem}}form{{border:1px solid #ddd;padding:1rem;margin-bottom:1rem;border-radius:8px}}label{{display:block;margin:.5rem 0 .25rem}}input[type=text],input[type=password],textarea,select{{width:100%;padding:.5rem}}button{{margin-top:.75rem;padding:.5rem 1rem}}.help-text{{font-size:0.85em;color:#666;margin-top:0.25rem}}</style>
    </head><body>
    <h1>Email API Configuration</h1>
    {f'<p style=\"color:green\">{message}</p>' if message else ''}
    
    <h2>Mail Provider Settings</h2>
    <form method="post" action="/admin/config/mail">
      <label>Mail Provider</label>
      <select name="mail_provider">
        <option value="gmail" {'selected' if mail_provider == 'gmail' else ''}>Gmail</option>
        <option value="ses" {'selected' if mail_provider == 'ses' else ''}>Amazon SES</option>
      </select>
      
      <label>Mail From Address</label>
      <input name="mail_from" type="text" value="{mail_from}" placeholder="noreply@example.com" />
      <div class="help-text">Email address to use as sender (optional for Gmail)</div>
      
      <h3 style="margin-top:1.5rem">Gmail Credentials</h3>
      <label>Gmail Address</label>
      <input name="gmail_user" type="text" value="{gmail_user}" placeholder="your-email@gmail.com" />
      <label>Gmail App Password (16 chars, no spaces)</label>
      <input name="gmail_app_password" type="password" value="" placeholder="••••••••••••••••" />
      <div class="help-text">Leave blank to keep existing password</div>
      
      <h3 style="margin-top:1.5rem">AWS SES Credentials</h3>
      <label>AWS Access Key ID</label>
      <input name="aws_access_key_id" type="text" value="" placeholder="AKIAIOSFODNN7EXAMPLE" />
      <div class="help-text">Leave blank to keep existing key</div>
      
      <label>AWS Secret Access Key</label>
      <input name="aws_secret_access_key" type="password" value="" placeholder="••••••••••••••••••••••••••••••••••••••••" />
      <div class="help-text">Leave blank to keep existing secret</div>
      
      <label>AWS Region</label>
      <input name="aws_region" type="text" value="{aws_region}" placeholder="us-east-1" />
      
      <button type="submit">Save Mail Settings</button>
    </form>

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

@app.post("/admin/config/mail")
async def admin_config_mail(
    mail_provider: str = Form("gmail"),
    mail_from: str = Form(""),
    gmail_user: str = Form(""),
    gmail_app_password: str = Form(""),
    aws_access_key_id: str = Form(""),
    aws_secret_access_key: str = Form(""),
    aws_region: str = Form(""),
    _: bool = Depends(_panel_auth),
):
    """Save mail provider configuration to mail_config.json"""
    # Load existing config
    current_config = load_mail_config()
    
    # Update only provided values (non-empty)
    if mail_provider:
        current_config['mail_provider'] = mail_provider.strip()
    if mail_from.strip():
        current_config['mail_from'] = mail_from.strip()
    
    # Gmail credentials
    if gmail_user.strip():
        current_config['gmail_user'] = gmail_user.strip()
    if gmail_app_password.strip():
        current_config['gmail_app_password'] = gmail_app_password.strip().replace(" ", "")
    
    # AWS SES credentials
    if aws_access_key_id.strip():
        current_config['aws_access_key_id'] = aws_access_key_id.strip()
    if aws_secret_access_key.strip():
        current_config['aws_secret_access_key'] = aws_secret_access_key.strip()
    if aws_region.strip():
        current_config['aws_region'] = aws_region.strip()
    
    # Save to mail_config.json
    save_mail_config(current_config)
    
    # Reload runtime configuration
    _reload_runtime_from_env()
    
    return HTMLResponse(content=_render_panel("Mail settings saved."))

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
    return HTMLResponse(content=_render_panel("Gmail settings saved."))

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