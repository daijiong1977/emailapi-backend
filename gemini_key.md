# Gemini API Key Proxy Extension

## Overview

Extend the AI Proxy Service to provide Gemini API key to authorized clients using a **session-based security model**. This allows the Swim Meet Builder app to access AI features on any browser/device without storing API keys locally.

**Key Benefits:**
- 🔐 **Session-Based Security**: API keys fetched per session, stored in memory only
- 🌐 **Cross-Device**: Works on any browser/device without manual configuration
- 🔄 **Auto-Cleanup**: Keys destroyed on tab close/refresh
- 🎯 **CORS Protected**: Only authorized domains can fetch keys
- 🚀 **Zero Persistence**: Never stored in localStorage or cookies

**Simple Design:**
- Admin provides **API key only**
- Client app handles all model selection and parameters
- No server-side AI configuration needed

## Implementation Requirements

### 1. Admin Panel Extension

Add simple Gemini API key section to the existing admin panel at `/admin/aiconfig`:

```
┌──────────────────────────────────────────────┐
│ Gemini API Key Configuration                 │
├──────────────────────────────────────────────┤
│ API Key:                                     │
│ [••••••••••••••••••••••••••••••••••••••]     │
│                                              │
│ Get your API key at:                         │
│ https://aistudio.google.com/app/apikey       │
│                                              │
│ [Test API Key] [Save Configuration]          │
│                                              │
│ Status: ✅ API Key Valid                     │
└──────────────────────────────────────────────┘
```

### 2. Server-Side Storage

Simple storage - just the API key:

```javascript
// Configuration structure
const GEMINI_CONFIG = {
  apiKey: process.env.GEMINI_API_KEY
};
```

### 3. API Endpoint

Add new endpoint to the existing proxy:

```
GET https://emailapi.6ray.com/ai/apikey
```

**No authentication required** (public endpoint, controlled by CORS)

### Response Format

```json
{
  "success": true,
  "apiKey": "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
}
```

**That's it!** Client app already has UI for model selection and parameters.

### Error Response

```json
{
  "success": false,
  "error": "Gemini API key not configured"
}
```

## Implementation Details

### Backend Code (Node.js/Express)

Simple and clean - just return the API key:

```javascript
// Route handler
app.get('/ai/apikey', (req, res) => {
  // Check if Gemini is configured
  if (!process.env.GEMINI_API_KEY) {
    return res.status(503).json({
      success: false,
      error: 'Gemini API key not configured'
    });
  }

  // Return API key only
  res.json({
    success: true,
    apiKey: process.env.GEMINI_API_KEY
  });
});
```

### CORS Configuration

Same CORS policy as GitHub token endpoint:

```javascript
// CORS configuration
const corsOptions = {
  origin: [
    'https://swimmeet.6ray.com',      // Production
    'http://localhost:5173',          // Local development (Vite)
    'http://localhost:3000'           // Local development (alternate)
  ],
  methods: ['GET', 'POST'],
  credentials: true
};

app.use(cors(corsOptions));
```

### Test API Key Function

Simple test - just verify the key works:

```javascript
// Test Gemini API key
async function testGeminiKey(apiKey) {
  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          contents: [{
            parts: [{ text: 'Hello! Respond with "OK" if you receive this.' }]
          }]
        })
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error?.message || `API returned ${response.status}`);
    }

    return {
      success: true,
      message: 'API key is valid'
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

Minimal - just API key input:

```html
<div class="config-section">
  <h3>Gemini API Configuration</h3>
  
  <div class="form-group">
    <label for="gemini-key">Gemini API Key:</label>
    <input 
      type="password" 
      id="gemini-key" 
      placeholder="AIzaSy••••••••••••••••••••••••••••"
      value="<%= config.geminiApiKey || '' %>"
    />
    <small>
      Get your API key at: 
      <a href="https://aistudio.google.com/app/apikey" target="_blank">
        Google AI Studio
      </a>
    </small>
  </div>

  <div class="button-group">
    <button onclick="testGemini()" class="btn-test">
      Test API Key
    </button>
    <button onclick="saveGeminiConfig()" class="btn-save">
      Save Configuration
    </button>
  </div>

  <div id="gemini-status" class="status-message"></div>
</div>
```

### JavaScript for Admin Panel

```javascript
async function testGemini() {
  const apiKey = document.getElementById('gemini-key').value;
  const statusDiv = document.getElementById('gemini-status');

  if (!apiKey) {
    statusDiv.innerHTML = '❌ Please enter an API key';
    statusDiv.className = 'status-message error';
    return;
  }

  statusDiv.innerHTML = '⏳ Testing API key...';
  statusDiv.className = 'status-message info';

  try {
    const response = await fetch('/admin/test-gemini', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ apiKey })
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

async function saveGeminiConfig() {
  const apiKey = document.getElementById('gemini-key').value;

  if (!apiKey) {
    alert('❌ Please enter an API key');
    return;
  }

  try {
    const response = await fetch('/admin/save-gemini', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ apiKey })
    });

    const result = await response.json();
    alert(result.success ? '✅ Configuration saved!' : `❌ ${result.error}`);
  } catch (error) {
    alert(`❌ Save failed: ${error.message}`);
  }
}
```

## Security Considerations

### 1. API Key Storage

Store securely in environment variables:

```javascript
// .env file
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### 2. CORS Protection

Only allow trusted domains to fetch the API key:

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

const apiKeyLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // 100 requests per window per IP
  message: 'Too many requests from this IP'
});

app.get('/ai/apikey', apiKeyLimiter, (req, res) => {
  // ... API key endpoint
});
```

### 4. Usage Monitoring

Track API usage to detect abuse:

```javascript
// Log API key fetches
app.get('/ai/apikey', (req, res) => {
  const clientIP = req.ip;
  const userAgent = req.headers['user-agent'];
  
  console.log(`[${new Date().toISOString()}] API key requested from ${clientIP} - ${userAgent}`);
  
  // ... rest of endpoint
});
```

## Testing

### Test Endpoint

```bash
# Test API key endpoint
curl https://emailapi.6ray.com/ai/apikey

# Expected response:
{
  "success": true,
  "apiKey": "AIzaSyXXXXXXXXXX"
}
```

### Test with Gemini API

```bash
# Use returned API key to call Gemini
API_KEY="AIzaSyXXXXXXXXXX"

curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=${API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{
    "contents": [{
      "parts": [{"text": "Hello!"}]
    }]
  }'
```

## Client Implementation (Swim Meet App)

The swim meet app will fetch the API key and use existing AI configuration UI:

```typescript
// Fetch AI key on app startup
async function loadAIKey() {
  try {
    const response = await fetch('https://emailapi.6ray.com/ai/apikey');
    const data = await response.json();
    
    if (data.success) {
      // Store in React state (memory only)
      setGeminiApiKey(data.apiKey);
    }
  } catch (error) {
    console.error('Failed to load AI key:', error);
  }
}

// Client app already has ConfigPanel with:
// - Model selection dropdown
// - Temperature slider
// - Max tokens input
// User controls all AI parameters from the UI
```

## Combined Startup Sequence

Fetch both GitHub token and AI key in parallel:

```typescript
// App.tsx - on component mount
useEffect(() => {
  async function initializeApp() {
    setLoading(true);
    
    try {
      // Fetch both in parallel
      const [githubRes, aiRes] = await Promise.all([
        fetch('https://emailapi.6ray.com/github/token'),
        fetch('https://emailapi.6ray.com/ai/apikey')
      ]);

      const githubData = await githubRes.json();
      const aiData = await aiRes.json();

      if (githubData.success) {
        setGitHubConfig({
          owner: githubData.config.owner,
          repo: githubData.config.repo,
          branch: githubData.config.branch,
          folder: githubData.config.basePath,
          token: githubData.token
        });
      }

      if (aiData.success) {
        setGeminiApiKey(aiData.apiKey);
      }

      setConfigured(true);
    } catch (error) {
      console.error('Failed to initialize:', error);
    } finally {
      setLoading(false);
    }
  }

  initializeApp();
}, []);
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 503 Service Unavailable | API key not configured | Configure in admin panel |
| 401 Unauthorized | Invalid API key | Generate new key from Google AI Studio |
| 429 Too Many Requests | Rate limit exceeded | Wait or upgrade quota |
| CORS Error | Origin not allowed | Add domain to CORS whitelist |

### Error Response

```json
{
  "success": false,
  "error": "Gemini API key not configured"
}
```

## Deployment Checklist

- [ ] Add `/ai/apikey` endpoint to proxy
- [ ] Add Gemini API key section to admin panel  
- [ ] Add test API key button
- [ ] Configure CORS to allow `swimmeet.6ray.com`
- [ ] Store API key securely (environment variable)
- [ ] Test endpoint returns API key
- [ ] Test API call to Gemini works
- [ ] Add rate limiting
- [ ] Update documentation

## Documentation

Add to `aiproxy.md`:

```markdown
## Gemini API Key Endpoint

Get Gemini API key for authorized clients.

**Endpoint:** `GET https://emailapi.6ray.com/ai/apikey`

**Response:**
```json
{
  "success": true,
  "apiKey": "AIzaSyXXXXX"
}
```

**Usage:**
```javascript
const response = await fetch('https://emailapi.6ray.com/ai/apikey');
const { apiKey } = await response.json();
// Client handles model selection and parameters
```
```

## Support

**For administrators:**
- Configure at: `https://emailapi.6ray.com/admin/aiconfig`
- Get API key from: https://aistudio.google.com/app/apikey
- Test API key before saving
- Add `swimmeet.6ray.com` to CORS whitelist

**For issues:**
- Check admin panel configuration
- Verify API key is valid
- Verify CORS settings
- Test with cURL first

## Summary

Simple, session-based AI access:

✅ **One endpoint**: `GET /ai/apikey`  
✅ **Just API key**: Client handles all configuration  
✅ **CORS protected**: Only authorized domains  
✅ **Session-based**: Fetched per session, memory only  
✅ **Client control**: Users choose models and parameters from UI  

**No server-side model configuration needed!** The swim meet app already has full AI configuration UI (ConfigPanel) where users choose models, temperature, etc.
