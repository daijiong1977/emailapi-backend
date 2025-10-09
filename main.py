from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
from contextlib import asynccontextmanager
from email_service import EmailService
from config import Config
from api_keys import init_db, verify_key, create_key, revoke_key, list_keys

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

DB_PATH = os.getenv("API_KEYS_DB", "./api_keys.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")  # for managing keys
ALLOW_DOMAINS = [d.strip().lower() for d in os.getenv("ALLOW_DOMAINS", "").split(",") if d.strip()]
BLOCK_DOMAINS = [d.strip().lower() for d in os.getenv("BLOCK_DOMAINS", "").split(",") if d.strip()]
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "771008")
ENV_FILE_PATH = os.getenv("ENV_FILE_PATH", ".env")

basic_security = HTTPBasic()

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
    allow = ",".join(ALLOW_DOMAINS)
    block = ",".join(BLOCK_DOMAINS)
    html = f"""
    <html><head><title>Email API Config</title>
    <style>body{{font-family:sans-serif;max-width:800px;margin:2rem auto;padding:0 1rem}}form{{border:1px solid #ddd;padding:1rem;margin-bottom:1rem;border-radius:8px}}label{{display:block;margin:.5rem 0 .25rem}}input[type=text],input[type=password],textarea{{width:100%;padding:.5rem}}button{{margin-top:.75rem;padding:.5rem 1rem}}</style>
    </head><body>
    <h1>Email API Configuration</h1>
    {f'<p style=\"color:green\">{message}</p>' if message else ''}
    <h2>Gmail Credentials</h2>
    <form method="post" action="/admin/config/gmail">
      <label>Gmail Address</label>
      <input name="gmail_user" type="text" value="{gmail_user}" />
      <label>App Password (16 chars, no spaces)</label>
      <input name="gmail_app_password" type="password" value="" placeholder="••••••••••••••••" />
      <button type="submit">Save Gmail Settings</button>
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)