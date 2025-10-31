from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header, status, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Annotated, List
import sqlite3
import os
import string
from datetime import datetime
from contextlib import asynccontextmanager
from email_service import EmailService
from config import Config
from ai_proxy import AIProxyService
from ai_providers import (
    add_ai_provider,
    get_enabled_provider,
    list_ai_providers,
    toggle_provider,
    delete_provider
)
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
ai_proxy = AIProxyService()

async def _reinitialize_email_service():
    """Reinitialize email service with current configuration."""
    global email_service
    email_service = EmailService()
    await email_service.initialize()

class EmailRequest(BaseModel):
    to_email: EmailStr
    subject: str
    message: str
    from_name: Optional[str] = None

class EmailResponse(BaseModel):
    success: bool
    message: str
    email_id: Optional[str] = None


class BulkEmailRequest(BaseModel):
    to_emails: List[EmailStr]
    subject: str
    message: str
    from_name: Optional[str] = None


class BulkEmailResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[dict]


class AIChatRequest(BaseModel):
    messages: List[dict]  # [{"role": "user", "content": "..."}]
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class AIChatResponse(BaseModel):
    success: bool
    response: Optional[dict] = None
    error: Optional[str] = None


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
# CORS settings for AI proxy - comma-separated origins, or "*" for all
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

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
    """Reload environment variables from .env file."""
    global ADMIN_TOKEN, ALLOW_DOMAINS, BLOCK_DOMAINS
    
    # Load current values from .env file
    env_map = _load_env_map()
    
    # Update os.environ with values from .env file
    for key, value in env_map.items():
        if value:
            os.environ[key] = value
    
    # Update global config variables
    config.gmail_user = env_map.get('GMAIL_USER', os.getenv('GMAIL_USER'))
    config.gmail_app_password = env_map.get('GMAIL_APP_PASSWORD', os.getenv('GMAIL_APP_PASSWORD'))
    
    # Update policies
    ADMIN_TOKEN = env_map.get('ADMIN_TOKEN', ADMIN_TOKEN)
    ALLOW_DOMAINS = [d.strip().lower() for d in (env_map.get('ALLOW_DOMAINS', '')).split(',') if d.strip()]
    BLOCK_DOMAINS = [d.strip().lower() for d in (env_map.get('BLOCK_DOMAINS', '')).split(',') if d.strip()]

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

# Add CORS middleware to allow cross-origin requests for AI proxy
# Configure via CORS_ORIGINS environment variable (comma-separated origins or "*" for all)
# Supports wildcard subdomains like *.6ray.com
if CORS_ORIGINS == "*":
    cors_origins = ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Parse origins and support wildcard patterns
    cors_list = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]
    
    # Check if any wildcard patterns exist
    has_wildcards = any("*" in origin for origin in cors_list)
    
    if has_wildcards:
        # Use regex patterns for wildcard support
        import re
        cors_patterns = []
        for origin in cors_list:
            if "*" in origin:
                # Convert wildcard pattern to regex
                pattern = origin.replace(".", r"\.").replace("*", r"[^/]+")
                cors_patterns.append(f"^{pattern}$")
            else:
                # Escape non-wildcard origins
                cors_patterns.append(re.escape(origin))
        
        # Use allow_origin_regex for wildcard support
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex="|".join(cors_patterns),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Use simple origins list
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


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

@app.post("/send-bulk-email", response_model=BulkEmailResponse, dependencies=[Depends(require_api_key)])
async def send_bulk_email(
    request: BulkEmailRequest,
    background_tasks: BackgroundTasks,
    username: str = Depends(require_api_key)
):
    """
    Send the same email to multiple recipients.
    
    Rate limits apply per provider:
    - Gmail: ~500 emails/day
    - Amazon SES: Check your quota (default 200/day sandbox, higher in production)
    
    Returns counts and per-recipient status.
    """
    # Check domain policy for all recipients
    for to_email in request.to_emails:
        try:
            _enforce_recipient_policy(to_email)
        except HTTPException as e:
            # If any recipient fails domain policy, fail the entire batch
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Domain policy violation for {to_email}: {e.detail}"
            )
    
    # Send to each recipient
    results = []
    successful = 0
    failed = 0
    
    for to_email in request.to_emails:
        try:
            # Send email synchronously to track individual results
            success = await email_service.send_email(
                to_email=to_email,
                subject=request.subject,
                message=request.message,
                from_name=request.from_name
            )
            
            if success:
                results.append({
                    "email": to_email,
                    "status": "success"
                })
                successful += 1
            else:
                results.append({
                    "email": to_email,
                    "status": "failed",
                    "error": "Send operation returned False"
                })
                failed += 1
                
        except Exception as e:
            results.append({
                "email": to_email,
                "status": "failed",
                "error": str(e)
            })
            failed += 1
    
    return BulkEmailResponse(
        total=len(request.to_emails),
        successful=successful,
        failed=failed,
        results=results
    )

@app.post("/ai/chat", response_model=AIChatResponse)
async def ai_chat(request: AIChatRequest):
    """
    Public AI chat completion proxy endpoint.
    
    No authentication required - allows any website/app to use the AI proxy.
    Supports OpenAI, Anthropic, Google AI, DeepSeek, and custom endpoints.
    API keys are hidden server-side for security.
    """
    # Get enabled provider
    provider = get_enabled_provider()
    if not provider:
        raise HTTPException(
            status_code=503,
            detail="No AI provider configured. Configure one in /admin/aiconfig"
        )
    
    try:
        # Prepare request parameters
        params = {
            "messages": request.messages
        }
        if request.model:
            params["model"] = request.model
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.max_tokens is not None:
            params["max_tokens"] = request.max_tokens
        
        # Make proxied request
        response = await ai_proxy.chat_completion(
            provider_type=provider["provider_type"],
            api_key=provider["api_key"],
            base_url=provider.get("base_url"),
            **params
        )
        
        return AIChatResponse(
            success=True,
            response=response
        )
        
    except Exception as e:
        return AIChatResponse(
            success=False,
            error=str(e)
        )

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
    cors_origins = env_vars.get('CORS_ORIGINS', '*')
    
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

    <h2>AI Proxy CORS Settings</h2>
    <form method="post" action="/admin/config/cors">
      <label>Allowed Origins (comma-separated URLs, or "*" for all)</label>
      <input name="cors_origins" type="text" value="{cors_origins}" placeholder="https://6ray.com,https://*.6ray.com,http://localhost:3000" />
      <div class="help-text">
        Control which websites can access your AI proxy API.<br>
        • Use <strong>*</strong> to allow all origins<br>
        • Wildcard subdomains supported: <strong>https://*.6ray.com</strong> (matches api.6ray.com, app.6ray.com, etc.)<br>
        • Multiple origins: <strong>https://6ray.com,https://*.6ray.com,http://localhost:3000</strong><br>
        • Local testing: <strong>http://localhost:3000,http://127.0.0.1:3000</strong><br>
        <br><strong>⚠️ Note:</strong> Service restart required for changes to take effect.
      </div>
      <button type="submit">Save CORS Settings</button>
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
    await _reinitialize_email_service()
    return HTMLResponse(content=_render_panel("Gmail settings saved and email service reloaded successfully!"))

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
    await _reinitialize_email_service()
    return HTMLResponse(content=_render_panel(f"Email provider switched to {provider.upper()} successfully!"))

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
    await _reinitialize_email_service()
    return HTMLResponse(content=_render_panel("Amazon SES settings saved and email service reloaded successfully!"))

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

@app.post("/admin/config/cors")
async def admin_config_cors(
    cors_origins: str = Form("*"),
    _: bool = Depends(_panel_auth),
):
    """Configure CORS allowed origins for AI proxy endpoint."""
    origins = cors_origins.strip()
    if not origins:
        origins = "*"
    
    _save_env_map({"CORS_ORIGINS": origins})
    _reload_runtime_from_env()
    
    # Attempt to restart the service automatically
    import subprocess
    try:
        result = subprocess.run(
            ["systemctl", "restart", "emailapi"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            msg = f"✅ CORS settings saved and service restarted successfully! New origins: <code>{origins}</code>"
        else:
            msg = f"⚠️ CORS settings saved but restart failed: {result.stderr}. Manual restart required: <code>sudo systemctl restart emailapi</code>"
    except subprocess.TimeoutExpired:
        msg = "⚠️ CORS settings saved but restart timed out. Manual restart may be required."
    except Exception as e:
        msg = f"⚠️ CORS settings saved but auto-restart failed: {str(e)}. Manual restart required: <code>sudo systemctl restart emailapi</code>"
    
    return HTMLResponse(content=_render_panel(msg))

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

# --- AI Admin Panel ---

def _render_ai_panel(msg: str = ""):
    """Render AI provider configuration panel."""
    providers = list_ai_providers(include_keys=False)
    
    # Load CORS configuration
    env_vars = _load_env_map()
    cors_origins = env_vars.get('CORS_ORIGINS', '*')
    
    provider_rows = ""
    for p in providers:
        enabled_badge = "✅ ENABLED" if p["enabled"] else "⚪"
        provider_rows += f"""
        <tr>
            <td>{p['name']}</td>
            <td>{p['provider_type']}</td>
            <td>{p['api_key']}</td>
            <td>{p['base_url'] or ''}</td>
            <td>{enabled_badge}</td>
            <td>
                <form method="post" action="/admin/aiconfig/toggle/{p['name']}" style="display:inline">
                    <button type="submit">{'Disable' if p['enabled'] else 'Enable'}</button>
                </form>
                <form method="post" action="/admin/aiconfig/delete/{p['name']}" style="display:inline" onsubmit="return confirm('Delete {p['name']}?')">
                    <button type="submit" style="background:#dc3545">Delete</button>
                </form>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html><head><title>AI Provider Configuration</title>
    <style>
      body{{font-family:sans-serif;max-width:1000px;margin:2rem auto;padding:1rem}}
      h1,h2{{color:#333}}
      form{{margin:1rem 0}}
      label{{display:block;margin:.5rem 0 .2rem}}
      input,select{{padding:.5rem;width:100%;max-width:400px;border:1px solid #ddd;border-radius:4px}}
      button{{padding:.5rem 1rem;background:#007bff;color:white;border:none;border-radius:4px;cursor:pointer;margin-right:.5rem}}
      button:hover{{background:#0056b3}}
      table{{width:100%;border-collapse:collapse;margin:1rem 0}}
      th,td{{padding:.5rem;text-align:left;border-bottom:1px solid #ddd}}
      th{{background:#f8f9fa}}
      .msg{{padding:1rem;margin:1rem 0;background:#d4edda;border:1px solid #c3e6cb;border-radius:4px}}
      .help-text{{font-size:0.85em;color:#666;margin-top:0.25rem}}
    </style>
    </head>
    <body>
    <h1>AI Provider Configuration</h1>
    <p><a href="/admin/config">← Back to Email Config</a></p>
    {'<div class="msg">' + msg + '</div>' if msg else ''}
    
    <h2>Add/Update AI Provider</h2>
    <form method="post" action="/admin/aiconfig/add">
      <label>Provider Name</label>
      <input name="name" type="text" placeholder="my-openai" required />
      <div class="help-text">Unique name for this provider</div>
      
      <label>Provider Type</label>
      <select name="provider_type" required>
        <option value="openai">OpenAI (GPT-4, GPT-3.5, etc.)</option>
        <option value="anthropic">Anthropic (Claude)</option>
        <option value="google">Google AI (Gemini)</option>
        <option value="deepseek">DeepSeek (DeepSeek-V3)</option>
        <option value="custom">Custom (OpenAI-compatible)</option>
      </select>
      
      <label>API Key</label>
      <input name="api_key" type="password" placeholder="sk-..." required />
      <div class="help-text">Provider API key</div>
      
      <label>Base URL (optional, for custom providers)</label>
      <input name="base_url" type="text" placeholder="https://api.example.com/v1/chat/completions" />
      <div class="help-text">Only needed for custom OpenAI-compatible endpoints</div>
      
      <button type="submit">Add/Update Provider</button>
    </form>
    
    <h2>Configured Providers</h2>
    <table>
      <tr>
        <th>Name</th>
        <th>Type</th>
        <th>API Key</th>
        <th>Base URL</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
      {provider_rows or '<tr><td colspan="6">No providers configured</td></tr>'}
    </table>
    
    <h2>CORS Settings</h2>
    <form method="post" action="/admin/aiconfig/cors">
      <label>Allowed Origins (comma-separated URLs, or "*" for all)</label>
      <input name="cors_origins" type="text" value="{cors_origins}" placeholder="https://6ray.com,https://*.6ray.com,http://localhost:3000" style="width:100%;padding:0.5rem;box-sizing:border-box" />
      <div class="help-text">
        Control which websites can access your AI proxy API.<br>
        • Use <strong>*</strong> to allow all origins (current: {cors_origins})<br>
        • Wildcard subdomains: <strong>https://*.6ray.com</strong> matches all subdomains<br>
        • Multiple origins: <strong>https://6ray.com,https://*.6ray.com,http://localhost:3000</strong><br>
        <br><strong>⚠️ Note:</strong> Service restart required for changes to take effect.
      </div>
      <button type="submit">Save CORS Settings</button>
    </form>
    
    <h2>Test AI Proxy</h2>
    <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
      <form method="post" action="/admin/aiconfig/test">
        <div class="help-text">Send test message "5+7 is what?" through the AI proxy</div>
        <button type="submit" style="background: #28a745;">Test AI Proxy</button>
      </form>
    </div>
    
    <h2>Public API Usage</h2>
    <p><strong>No API key required!</strong> The <code>/ai/chat</code> endpoint is public and can be used from any website or application.</p>
    
    <h3>API Endpoint:</h3>
    <p><code>POST https://emailapi.6ray.com/ai/chat</code></p>
    
    <h3>cURL Example:</h3>
    <pre style="background:#f8f9fa;padding:1rem;border-radius:4px;overflow:auto">
curl -X POST https://emailapi.6ray.com/ai/chat \\
  -H "Content-Type: application/json" \\
  -d '{{
    "messages": [{{"role": "user", "content": "Hello!"}}]
  }}'
    </pre>
    
    <h3>JavaScript/Fetch Example:</h3>
    <pre style="background:#f8f9fa;padding:1rem;border-radius:4px;overflow:auto">
fetch('https://emailapi.6ray.com/ai/chat', {{
  method: 'POST',
  headers: {{'Content-Type': 'application/json'}},
  body: JSON.stringify({{
    messages: [{{"role": "user", "content": "Hello!"}}]
  }})
}})
.then(res => res.json())
.then(data => console.log(data.response));
    </pre>
    
    </body></html>
    """
    return html

@app.get("/admin/aiconfig", response_class=HTMLResponse)
async def ai_admin_panel(_: bool = Depends(_panel_auth)):
    return HTMLResponse(content=_render_ai_panel())

@app.post("/admin/aiconfig/add")
async def ai_admin_add_provider(
    name: str = Form(...),
    provider_type: str = Form(...),
    api_key: str = Form(...),
    base_url: str = Form(""),
    _: bool = Depends(_panel_auth)
):
    base_url = base_url.strip() if base_url else None
    success = add_ai_provider(name, provider_type, api_key, base_url, enabled=False)
    msg = f"Provider '{name}' added successfully!" if success else "Failed to add provider"
    return HTMLResponse(content=_render_ai_panel(msg))

@app.post("/admin/aiconfig/toggle/{name}")
async def ai_admin_toggle_provider(name: str, _: bool = Depends(_panel_auth)):
    # Get current provider to determine new state
    providers = list_ai_providers()
    current = next((p for p in providers if p["name"] == name), None)
    if not current:
        return HTMLResponse(content=_render_ai_panel(f"Provider '{name}' not found"))
    
    new_state = not current["enabled"]
    success = toggle_provider(name, new_state)
    msg = f"Provider '{name}' {'enabled' if new_state else 'disabled'}" if success else "Failed to toggle provider"
    return HTMLResponse(content=_render_ai_panel(msg))

@app.post("/admin/aiconfig/delete/{name}")
async def ai_admin_delete_provider(name: str, _: bool = Depends(_panel_auth)):
    success = delete_provider(name)
    msg = f"Provider '{name}' deleted" if success else "Failed to delete provider"
    return HTMLResponse(content=_render_ai_panel(msg))

@app.post("/admin/aiconfig/cors")
async def ai_admin_config_cors(
    cors_origins: str = Form("*"),
    _: bool = Depends(_panel_auth),
):
    """Configure CORS allowed origins for AI proxy endpoint."""
    origins = cors_origins.strip()
    if not origins:
        origins = "*"
    
    _save_env_map({"CORS_ORIGINS": origins})
    _reload_runtime_from_env()
    
    # Attempt to restart the service automatically
    import subprocess
    try:
        result = subprocess.run(
            ["systemctl", "restart", "emailapi"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            msg = f"✅ CORS settings saved and service restarted successfully! New origins: <code>{origins}</code>"
        else:
            msg = f"⚠️ CORS settings saved but restart failed: {result.stderr}. Manual restart required: <code>sudo systemctl restart emailapi</code>"
    except subprocess.TimeoutExpired:
        msg = "⚠️ CORS settings saved but restart timed out. Manual restart may be required."
    except Exception as e:
        msg = f"⚠️ CORS settings saved but auto-restart failed: {str(e)}. Manual restart required: <code>sudo systemctl restart emailapi</code>"
    
    return HTMLResponse(content=_render_ai_panel(msg))

@app.post("/admin/aiconfig/test")
async def ai_admin_test_proxy(_: bool = Depends(_panel_auth)):
    """Test the AI proxy with a simple message."""
    try:
        # Get enabled provider
        provider = get_enabled_provider()
        if not provider:
            return HTMLResponse(content=_render_ai_panel("❌ No AI provider enabled. Please enable a provider first."))
        
        # Initialize AI proxy
        test_proxy = AIProxyService()
        
        # Send test message
        response = await test_proxy.chat_completion(
            provider_type=provider["provider_type"],
            api_key=provider["api_key"],
            messages=[{"role": "user", "content": "5+7 is what?"}],
            model=None,  # Use default model
            base_url=provider.get("base_url"),
            temperature=None,
            max_tokens=None
        )
        
        # Extract content from response based on provider format
        content = ""
        if "choices" in response:  # OpenAI/DeepSeek format
            content = response["choices"][0]["message"]["content"]
        elif "content" in response:  # Anthropic format
            if isinstance(response["content"], list):
                content = response["content"][0].get("text", str(response["content"]))
            else:
                content = response["content"]
        elif "candidates" in response:  # Google format
            content = response["candidates"][0]["content"]["parts"][0]["text"]
        else:
            content = str(response)
        
        msg = f"✅ Test successful using provider '{provider['name']}' ({provider['provider_type']})!<br><br><strong>Response:</strong><br><pre style='background:#f8f9fa;padding:1rem;border-radius:4px;white-space:pre-wrap'>{content}</pre>"
        return HTMLResponse(content=_render_ai_panel(msg))
        
    except Exception as e:
        import traceback
        error_detail = f"{str(e)}<br><br><pre style='font-size:0.85em'>{traceback.format_exc()}</pre>"
        return HTMLResponse(content=_render_ai_panel(f"❌ Test failed: {error_detail}"))

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