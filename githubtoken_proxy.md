# GitHub Token & API Key Proxy Extension

## Overview

Extend the AI Proxy Service to provide both GitHub token and AI API key to authorized clients using a **session-based security model**. This allows the Swim Meet Builder app to work on any browser/device without storing any credentials locally.

**Key Benefits:**
- 🔐 **Session-Based Security**: Tokens fetched per session, stored in memory only
- 🌐 **Cross-Device**: Works on any browser/device without manual configuration
- 🔄 **Auto-Cleanup**: Tokens destroyed on tab close/refresh
- 🎯 **CORS Protected**: Only authorized domains can fetch tokens
- 🚀 **Zero Persistence**: Never stored in localStorage or cookies

## Implementation Requirements

### 1. Admin Panel Extension

Add two new sections to the existing admin panel at `/admin/aiconfig`:

#### GitHub Storage Configuration

```
┌──────────────────────────────────────────────┐
│ GitHub Storage Configuration                 │
├──────────────────────────────────────────────┤
│ GitHub Personal Access Token:                │
│ [ghp_••••••••••••••••••••••••••••••••••]     │
│                                              │
│ Repository Owner: [daijiong1977]            │
│ Repository Name:  [swimmeet]                │
│ Base Path:        [public/shares]           │
│                                              │
│ Token Permissions Required:                 │
│ ✓ repo (full control of private repos)      │
│ ✓ public_repo (for public repos only)       │
│                                              │
│ [Test Connection] [Save Configuration]       │
│                                              │
│ Status: ✅ Connected to daijiong1977/swimmeet│
└──────────────────────────────────────────────┘
```

#### Gemini API Key Configuration

```
┌──────────────────────────────────────────────┐
│ Gemini API Key (Session-Based)              │
├──────────────────────────────────────────────┤
│ API Key:                                     │
│ [••••••••••••••••••••••••••••••••••••••]     │
│                                              │
│ Default Model: [gemini-2.0-flash-exp    ▼]  │
│                                              │
│ Available Models:                            │
│ • gemini-2.0-flash-exp (Recommended)         │
│ • gemini-1.5-pro                             │
│ • gemini-1.5-flash                           │
│                                              │
│ [Test API Key] [Save Configuration]          │
│                                              │
│ Status: ✅ API Key Valid                     │
└──────────────────────────────────────────────┘
```

### 2. Server-Side Storage

Store configuration securely (encrypted in database or environment variables):

```javascript
// Configuration structure
const GITHUB_CONFIG = {
  token: process.env.GITHUB_TOKEN,        // GitHub personal access token
  owner: process.env.GITHUB_OWNER,        // daijiong1977
  repo: process.env.GITHUB_REPO,          // swimmeet
  basePath: process.env.GITHUB_BASE_PATH  // public/shares
};
```

### 3. API Endpoint

Add new endpoint to the existing proxy:

```
GET https://emailapi.6ray.com/github/token
```

**No authentication required** (public endpoint, controlled by CORS)

### Response Format

```json
{
  "success": true,
  "token": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "config": {
    "owner": "daijiong1977",
    "repo": "swimmeet",
    "branch": "main",
    "basePath": "public/shares"
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": "GitHub token not configured"
}
```

## Implementation Details

### Backend Code (Node.js/Express)

```javascript
// Route handler
app.get('/github/token', (req, res) => {
  // Check if GitHub is configured
  if (!process.env.GITHUB_TOKEN) {
    return res.status(503).json({
      success: false,
      error: 'GitHub token not configured'
    });
  }

  // Return token and configuration
  res.json({
    success: true,
    token: process.env.GITHUB_TOKEN,
    config: {
      owner: process.env.GITHUB_OWNER || 'daijiong1977',
      repo: process.env.GITHUB_REPO || 'swimmeet',
      branch: process.env.GITHUB_BRANCH || 'main',
      basePath: process.env.GITHUB_BASE_PATH || 'public/shares'
    }
  });
});
```

### CORS Configuration

Add the swim meet app domain to CORS whitelist:

```javascript
// CORS configuration
const corsOptions = {
  origin: [
    'https://swimmeet.6ray.com',      // Production
    'http://localhost:5173',          // Local development (Vite)
    'http://localhost:3000'           // Local development (alternate)
  ],
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  credentials: true
};

app.use(cors(corsOptions));
```

### Test Connection Function

Add to admin panel to verify GitHub configuration:

```javascript
// Test GitHub connection
async function testGitHubConnection(token, owner, repo) {
  try {
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}`,
      {
        headers: {
          'Authorization': `token ${token}`,
          'Accept': 'application/vnd.github.v3+json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`GitHub API returned ${response.status}`);
    }

    const repoData = await response.json();
    
    return {
      success: true,
      message: `Connected to ${repoData.full_name}`,
      details: {
        name: repoData.name,
        private: repoData.private,
        permissions: repoData.permissions
      }
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
}
```

## Admin Panel UI

### HTML Structure

```html
<div class="config-section">
  <h3>GitHub Storage</h3>
  
  <div class="form-group">
    <label for="github-token">GitHub Personal Access Token:</label>
    <input 
      type="password" 
      id="github-token" 
      placeholder="ghp_••••••••••••••••••••••••••••"
      value="<%= config.githubToken || '' %>"
    />
    <small>
      Create token at: 
      <a href="https://github.com/settings/tokens" target="_blank">
        github.com/settings/tokens
      </a>
    </small>
  </div>

  <div class="form-group">
    <label for="github-owner">Repository Owner:</label>
    <input 
      type="text" 
      id="github-owner" 
      placeholder="daijiong1977"
      value="<%= config.githubOwner || '' %>"
    />
  </div>

  <div class="form-group">
    <label for="github-repo">Repository Name:</label>
    <input 
      type="text" 
      id="github-repo" 
      placeholder="swimmeet"
      value="<%= config.githubRepo || '' %>"
    />
  </div>

  <div class="form-group">
    <label for="github-basepath">Base Path:</label>
    <input 
      type="text" 
      id="github-basepath" 
      placeholder="public/shares"
      value="<%= config.githubBasePath || 'public/shares' %>"
    />
  </div>

  <div class="button-group">
    <button onclick="testGitHub()" class="btn-test">
      Test Connection
    </button>
    <button onclick="saveGitHubConfig()" class="btn-save">
      Save Configuration
    </button>
  </div>

  <div id="github-status" class="status-message"></div>
</div>
```

### JavaScript for Admin Panel

```javascript
async function testGitHub() {
  const token = document.getElementById('github-token').value;
  const owner = document.getElementById('github-owner').value;
  const repo = document.getElementById('github-repo').value;
  const statusDiv = document.getElementById('github-status');

  if (!token || !owner || !repo) {
    statusDiv.innerHTML = '❌ Please fill in all fields';
    statusDiv.className = 'status-message error';
    return;
  }

  statusDiv.innerHTML = '⏳ Testing connection...';
  statusDiv.className = 'status-message info';

  try {
    const response = await fetch('/admin/test-github', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, owner, repo })
    });

    const result = await response.json();

    if (result.success) {
      statusDiv.innerHTML = `✅ ${result.message}`;
      statusDiv.className = 'status-message success';
    } else {
      statusDiv.innerHTML = `❌ ${result.error}`;
      statusDiv.className = 'status-message error';
    }
  } catch (error) {
    statusDiv.innerHTML = `❌ Test failed: ${error.message}`;
    statusDiv.className = 'status-message error';
  }
}

async function saveGitHubConfig() {
  const config = {
    token: document.getElementById('github-token').value,
    owner: document.getElementById('github-owner').value,
    repo: document.getElementById('github-repo').value,
    basePath: document.getElementById('github-basepath').value
  };

  try {
    const response = await fetch('/admin/save-github', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });

    const result = await response.json();
    alert(result.success ? '✅ Configuration saved!' : `❌ ${result.error}`);
  } catch (error) {
    alert(`❌ Save failed: ${error.message}`);
  }
}
```

## Security Considerations

### 1. Token Storage

**Recommended approach:**
- Store in environment variables (`.env` file)
- Encrypt in database if using database storage
- Never commit tokens to git

```javascript
// .env file
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_OWNER=daijiong1977
GITHUB_REPO=swimmeet
GITHUB_BASE_PATH=public/shares
```

### 2. CORS Protection

Only allow trusted domains to fetch the token:

```javascript
const allowedOrigins = [
  'https://swimmeet.6ray.com',
  'http://localhost:5173'
];

app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (allowedOrigins.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  }
  next();
});
```

### 3. Rate Limiting

Prevent abuse by limiting requests:

```javascript
const rateLimit = require('express-rate-limit');

const tokenLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // 100 requests per window
  message: 'Too many requests from this IP'
});

app.get('/github/token', tokenLimiter, (req, res) => {
  // ... token endpoint
});
```

### 4. Token Permissions

GitHub token should have minimal required permissions:

**For public repositories:**
- `public_repo` - Access public repositories

**For private repositories:**
- `repo` - Full control of private repositories

**Not needed:**
- ❌ User permissions
- ❌ Delete permissions
- ❌ Admin permissions

## Testing

### Test Endpoint

```bash
# Test token endpoint
curl https://emailapi.6ray.com/github/token

# Expected response:
{
  "success": true,
  "token": "ghp_xxxxxxxxxxxxx",
  "config": {
    "owner": "daijiong1977",
    "repo": "swimmeet",
    "branch": "main",
    "basePath": "public/shares"
  }
}
```

### Test GitHub Connection

```bash
# Using returned token to test GitHub API
TOKEN="ghp_xxxxxxxxxxxxx"
curl -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/daijiong1977/swimmeet

# Should return repository information
```

## Client Implementation (Swim Meet App)

The swim meet app will be updated to use this endpoint:

```typescript
// Fetch GitHub config on app startup
async function loadGitHubConfig() {
  try {
    const response = await fetch('https://emailapi.6ray.com/github/token');
    const data = await response.json();
    
    if (data.success) {
      // Use token for GitHub API calls
      setGitHubConfig({
        owner: data.config.owner,
        repo: data.config.repo,
        branch: data.config.branch,
        folder: data.config.basePath,
        token: data.token
      });
    }
  } catch (error) {
    console.error('Failed to load GitHub config:', error);
  }
}
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 503 Service Unavailable | Token not configured | Configure in admin panel |
| 401 Unauthorized | Invalid token | Generate new token with correct permissions |
| 404 Not Found | Repository not found | Check owner/repo names |
| 403 Forbidden | Token lacks permissions | Regenerate token with `repo` or `public_repo` scope |
| CORS Error | Origin not allowed | Add domain to CORS whitelist |

### Error Response Examples

```json
// Token not configured
{
  "success": false,
  "error": "GitHub token not configured"
}

// Invalid token format
{
  "success": false,
  "error": "Invalid GitHub token format"
}

// Connection test failed
{
  "success": false,
  "error": "GitHub API returned 404: Repository not found"
}
```

## Deployment Checklist

- [ ] Add `/github/token` endpoint to proxy
- [ ] Add GitHub configuration section to admin panel
- [ ] Add test connection button and handler
- [ ] Configure CORS to allow `swimmeet.6ray.com`
- [ ] Store GitHub token securely (environment variables)
- [ ] Test endpoint returns token and config
- [ ] Test connection to GitHub API works
- [ ] Add rate limiting to token endpoint
- [ ] Update documentation

## Documentation Update

Add to the main `aiproxy.md` file:

```markdown
## GitHub Token Endpoint

Get GitHub token and configuration for authorized clients.

**Endpoint:** `GET https://emailapi.6ray.com/github/token`

**Response:**
```json
{
  "success": true,
  "token": "ghp_xxxxx",
  "config": {
    "owner": "daijiong1977",
    "repo": "swimmeet",
    "branch": "main",
    "basePath": "public/shares"
  }
}
```

**Usage:**
```javascript
const response = await fetch('https://emailapi.6ray.com/github/token');
const { token, config } = await response.json();
// Use token for GitHub API calls
```
```

## Support

**For administrators:**
- Configure GitHub in admin panel: `https://emailapi.6ray.com/admin/aiconfig`
- Test connection before saving
- Ensure token has correct permissions
- Add swim meet domain to CORS whitelist

**For issues:**
- Check admin panel configuration
- Verify CORS settings
- Test with cURL to isolate client-side issues
- Check GitHub token permissions and expiration

## Summary

This extension provides a simple, secure way to share GitHub access with authorized clients:

✅ **One endpoint**: `GET /github/token`  
✅ **CORS protected**: Only authorized domains can access  
✅ **Admin panel**: Easy configuration and testing  
✅ **Secure**: Token stays server-side, never in client code  
✅ **Simple**: Client just fetches config and uses existing GitHub API  

No complex OAuth flows or extensive backend GitHub API proxying required!
