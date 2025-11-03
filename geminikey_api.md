# Gemini API Key Proxy API

## Overview

The Gemini API Key Proxy provides secure, session-based access to Google's Gemini AI API without storing API keys in client applications. The proxy returns the API key to authorized domains via CORS protection, allowing client apps to handle all model selection and parameters directly.

**Base URL:** `https://emailapi.6ray.com`

**Key Features:**
- 🔐 **Session-Based Security**: API key fetched per session, no local storage
- 🌐 **Cross-Device**: Works on any browser/device without configuration
- 🎯 **CORS Protected**: Only authorized domains can access the key
- 🚀 **Zero Persistence**: Never stored in localStorage or cookies
- 💡 **Client Control**: Client app handles all model selection and parameters
- ✅ **Easy Admin**: Configure via web panel at `/admin/aiconfig`

---

## API Endpoints

### Get Gemini API Key

Retrieve Gemini API key for authorized clients. No proxy - just returns the key for client-side use.

**Endpoint:** `GET /ai/apikey`

**Authentication:** None required (controlled by CORS)

**Request:**

```bash
curl https://emailapi.6ray.com/ai/apikey
```

**Success Response (200 OK):**

```json
{
  "success": true,
  "apiKey": "AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
}
```

**Error Response (503 Service Unavailable):**

```json
{
  "detail": "Gemini API key not configured"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Operation success status |
| `apiKey` | string | Google Gemini API key |

---

## Client Implementation

### JavaScript/TypeScript Example

```typescript
// Fetch Gemini API key on app startup
async function loadGeminiKey() {
  try {
    const response = await fetch('https://emailapi.6ray.com/ai/apikey');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (data.success) {
      // Store in memory for session
      window.geminiApiKey = data.apiKey;
      console.log('Gemini API key loaded');
      return data.apiKey;
    }
  } catch (error) {
    console.error('Failed to load Gemini API key:', error);
    throw error;
  }
}

// Use API key to call Gemini directly
async function callGemini(prompt, model = 'gemini-2.5-flash', temperature = 1.0, maxTokens = 2048) {
  const apiKey = window.geminiApiKey;
  
  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        contents: [{
          parts: [{ text: prompt }]
        }],
        generationConfig: {
          temperature: temperature,
          maxOutputTokens: maxTokens
        }
      })
    }
  );
  
  const result = await response.json();
  return result.candidates[0].content.parts[0].text;
}

// Initialize on page load
loadGeminiKey().then(key => {
  console.log('Gemini ready!');
}).catch(err => {
  console.error('Gemini initialization failed:', err);
});
```

### React Example with State Management

```typescript
import { useEffect, useState } from 'react';

interface GeminiConfig {
  apiKey: string;
  model: string;
  temperature: number;
  maxTokens: number;
}

export function useGemini() {
  const [config, setConfig] = useState<GeminiConfig>({
    apiKey: '',
    model: 'gemini-2.5-flash',
    temperature: 1.0,
    maxTokens: 2048
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('https://emailapi.6ray.com/ai/apikey')
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch Gemini API key');
        return res.json();
      })
      .then(data => {
        if (data.success) {
          setConfig(prev => ({ ...prev, apiKey: data.apiKey }));
        }
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const generate = async (prompt: string) => {
    if (!config.apiKey) {
      throw new Error('API key not loaded');
    }

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${config.model}:generateContent?key=${config.apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            temperature: config.temperature,
            maxOutputTokens: config.maxTokens
          }
        })
      }
    );

    const result = await response.json();
    return result.candidates[0].content.parts[0].text;
  };

  return { config, setConfig, generate, loading, error };
}

// Usage in component
function App() {
  const { config, setConfig, generate, loading, error } = useGemini();
  const [response, setResponse] = useState('');

  const handleGenerate = async () => {
    const result = await generate('What is 5+7?');
    setResponse(result);
  };

  if (loading) return <div>Loading Gemini...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!config.apiKey) return <div>Gemini not configured</div>;

  return (
    <div>
      <h1>Gemini AI</h1>
      
      {/* Model Selection */}
      <select 
        value={config.model} 
        onChange={(e) => setConfig(prev => ({ ...prev, model: e.target.value }))}
      >
        <option value="gemini-2.5-flash">Gemini 2.5 Flash (Fastest)</option>
        <option value="gemini-2.5-pro">Gemini 2.5 Pro (Best Quality)</option>
        <option value="gemini-2.0-flash-exp">Gemini 2.0 Flash Experimental</option>
      </select>

      {/* Temperature Slider */}
      <label>
        Temperature: {config.temperature}
        <input
          type="range"
          min="0"
          max="2"
          step="0.1"
          value={config.temperature}
          onChange={(e) => setConfig(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
        />
      </label>

      {/* Max Tokens */}
      <label>
        Max Tokens:
        <input
          type="number"
          value={config.maxTokens}
          onChange={(e) => setConfig(prev => ({ ...prev, maxTokens: parseInt(e.target.value) }))}
        />
      </label>

      <button onClick={handleGenerate}>Generate</button>
      
      {response && <div>Response: {response}</div>}
    </div>
  );
}
```

### Combined Initialization (GitHub + Gemini)

```typescript
// Fetch both GitHub token and Gemini API key in parallel
async function initializeApp() {
  try {
    const [githubRes, geminiRes] = await Promise.all([
      fetch('https://emailapi.6ray.com/github/token'),
      fetch('https://emailapi.6ray.com/ai/apikey')
    ]);

    const githubData = await githubRes.json();
    const geminiData = await geminiRes.json();

    const config = {
      github: null,
      gemini: null
    };

    if (githubData.success) {
      config.github = {
        owner: githubData.config.owner,
        repo: githubData.config.repo,
        branch: githubData.config.branch,
        basePath: githubData.config.basePath,
        token: githubData.token
      };
    }

    if (geminiData.success) {
      config.gemini = {
        apiKey: geminiData.apiKey
      };
    }

    return config;
  } catch (error) {
    console.error('Failed to initialize:', error);
    throw error;
  }
}

// Usage
initializeApp().then(config => {
  console.log('App initialized with GitHub and Gemini');
  // Both services ready to use
}).catch(err => {
  console.error('Initialization failed:', err);
});
```

### cURL Example

```bash
# Fetch API key
curl -X GET https://emailapi.6ray.com/ai/apikey

# Use key to call Gemini API
API_KEY="AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

# Simple text generation
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "contents": [{
      "parts": [{"text": "What is the capital of France?"}]
    }]
  }'

# With generation config
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "contents": [{
      "parts": [{"text": "Write a short poem about coding"}]
    }],
    "generationConfig": {
      "temperature": 1.0,
      "maxOutputTokens": 1024
    }
  }'
```

---

## Available Gemini Models

### Current Models (as of November 2025)

**Recommended Models:**

| Model | Description | Best For |
|-------|-------------|----------|
| `gemini-2.5-flash` | Latest fast model | General use, quick responses |
| `gemini-2.5-pro` | Latest quality model | Complex tasks, best quality |
| `gemini-2.0-flash-exp` | Experimental flash | Testing new features |

**All Available Models:**

```
gemini-2.5-flash              ← Recommended (Fast)
gemini-2.5-pro                ← Recommended (Quality)
gemini-2.5-flash-lite-preview-06-17
gemini-2.5-pro-preview-03-25
gemini-2.5-pro-preview-05-06
gemini-2.5-pro-preview-06-05
gemini-2.5-flash-preview-05-20
gemini-2.0-flash              
gemini-2.0-flash-exp          ← Experimental
gemini-2.0-flash-001
gemini-2.0-flash-lite
gemini-2.0-flash-lite-001
gemini-2.0-pro-exp
gemini-2.0-pro-exp-02-05
gemini-exp-1206
```

**List models programmatically:**

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_API_KEY"
```

---

## Generation Configuration

### Parameters

| Parameter | Type | Range | Default | Description |
|-----------|------|-------|---------|-------------|
| `temperature` | float | 0.0-2.0 | 1.0 | Controls randomness (lower = more focused) |
| `maxOutputTokens` | integer | 1-8192 | 2048 | Maximum tokens in response |
| `topK` | integer | 1-40 | 40 | Top-K sampling |
| `topP` | float | 0.0-1.0 | 0.95 | Top-P (nucleus) sampling |

### Example with All Parameters

```javascript
const response = await fetch(
  `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{
        parts: [{ text: 'Your prompt here' }]
      }],
      generationConfig: {
        temperature: 0.9,
        maxOutputTokens: 2048,
        topK: 40,
        topP: 0.95
      }
    })
  }
);
```

---

## Admin Configuration

### Access Admin Panel

Navigate to: `https://emailapi.6ray.com/admin/aiconfig`

### Gemini API Configuration Section

**Required Fields:**

1. **Gemini API Key**
   - Generate at: [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Free tier available with rate limits
   - No credit card required for testing

**Actions:**

- **Test Gemini API Key**: Verifies the key works by sending a test request
- **Save Gemini API Key**: Saves the key to server (stores in .env file)

### Getting an API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated key (starts with `AIzaSy...`)
5. Paste into admin panel
6. Click "Test Gemini API Key" to verify
7. Click "Save Gemini API Key" to store

---

## CORS Configuration

### Allowed Origins

Configure which domains can access the Gemini API key endpoint via the admin panel's CORS settings.

**Default:** `*` (all origins - not recommended for production)

**Recommended Production Settings:**

```
https://*.6ray.com,http://localhost:5173,http://localhost:3000
```

This allows:
- All subdomains of `6ray.com` (e.g., `swimmeet.6ray.com`)
- Local development on ports 5173 (Vite) and 3000 (Create React App)

**Update CORS:**

1. Go to admin panel: `https://emailapi.6ray.com/admin/aiconfig`
2. Scroll to **CORS Settings** section
3. Enter allowed origins (comma-separated)
4. Click **Save CORS Settings**
5. Service will restart automatically

---

## Security Considerations

### API Key Storage

✅ **Server-Side (.env file):**
```bash
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

❌ **Never commit keys to git:**
- Add `.env` to `.gitignore`
- Use environment variables in production
- Rotate keys regularly
- Monitor usage in Google AI Studio

### CORS Protection

The endpoint has **no authentication** but is protected by CORS:

- Only whitelisted domains can call the endpoint from browsers
- Direct API calls (curl, Postman) always work
- Configure CORS in admin panel to restrict access

### Rate Limiting

Google Gemini API has built-in rate limits:

**Free Tier:**
- 15 requests per minute (RPM)
- 1 million tokens per minute (TPM)
- 1,500 requests per day (RPD)

**Paid Tier:**
- Higher limits based on plan
- Check [Google AI Studio](https://aistudio.google.com/) for details

### Best Practices

1. **Monitor Usage**: Check API usage in Google AI Studio dashboard
2. **Set Reasonable Limits**: Use `maxOutputTokens` to control costs
3. **Handle Errors**: Implement retry logic with exponential backoff
4. **Cache Results**: Cache responses when appropriate
5. **Rotate Keys**: Update keys periodically via admin panel
6. **Restrict CORS**: Only allow necessary domains

---

## Error Handling

### Common Errors

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| Gemini API key not configured | 503 | Key not set in admin panel | Configure in admin panel |
| CORS error | - | Origin not whitelisted | Add domain to CORS settings |
| 400 Bad Request | 400 | Invalid request format | Check request JSON structure |
| 403 Forbidden | 403 | Invalid or expired API key | Generate new key from Google AI Studio |
| 404 Not Found | 404 | Model not available | Use valid model name (gemini-2.5-flash) |
| 429 Too Many Requests | 429 | Rate limit exceeded | Wait and retry, or upgrade plan |
| 500 Internal Server Error | 500 | Gemini API issue | Check status.cloud.google.com |

### Error Response Format

**Server Error (503):**
```json
{
  "detail": "Gemini API key not configured"
}
```

**CORS Error (Browser Console):**
```
Access to fetch at 'https://emailapi.6ray.com/ai/apikey' from origin 
'https://example.com' has been blocked by CORS policy
```

**Gemini API Error (400):**
```json
{
  "error": {
    "code": 400,
    "message": "Invalid request",
    "status": "INVALID_ARGUMENT"
  }
}
```

**Rate Limit Error (429):**
```json
{
  "error": {
    "code": 429,
    "message": "Resource has been exhausted (e.g. check quota).",
    "status": "RESOURCE_EXHAUSTED"
  }
}
```

### Error Handling Example

```typescript
async function callGeminiSafe(prompt: string) {
  try {
    // Fetch API key
    const keyResponse = await fetch('https://emailapi.6ray.com/ai/apikey');
    
    if (keyResponse.status === 503) {
      console.error('Gemini not configured on server');
      return { error: 'Service not configured' };
    }
    
    if (!keyResponse.ok) {
      throw new Error(`HTTP ${keyResponse.status}: ${keyResponse.statusText}`);
    }
    
    const { apiKey } = await keyResponse.json();
    
    // Call Gemini API
    const geminiResponse = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }]
        })
      }
    );
    
    if (geminiResponse.status === 429) {
      // Rate limit - wait and retry
      await new Promise(resolve => setTimeout(resolve, 2000));
      return callGeminiSafe(prompt); // Retry once
    }
    
    if (!geminiResponse.ok) {
      const error = await geminiResponse.json();
      throw new Error(error.error?.message || 'Gemini API error');
    }
    
    const result = await geminiResponse.json();
    return {
      text: result.candidates[0].content.parts[0].text,
      model: result.modelVersion
    };
    
  } catch (error) {
    console.error('Gemini error:', error);
    return { error: error.message };
  }
}
```

---

## Testing

### Test API Key Endpoint

```bash
# Test endpoint is accessible
curl -I https://emailapi.6ray.com/ai/apikey

# Test with configured key
curl https://emailapi.6ray.com/ai/apikey | jq

# Test Gemini API with returned key
API_KEY=$(curl -s https://emailapi.6ray.com/ai/apikey | jq -r '.apiKey')
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"Say hello"}]}]}'
```

### Test from Browser Console

```javascript
// Test API key endpoint
fetch('https://emailapi.6ray.com/ai/apikey')
  .then(r => r.json())
  .then(d => console.log('API Key:', d.apiKey))
  .catch(e => console.error(e));

// Test full Gemini call
fetch('https://emailapi.6ray.com/ai/apikey')
  .then(r => r.json())
  .then(async data => {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${data.apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: 'What is 2+2?' }] }]
        })
      }
    );
    return response.json();
  })
  .then(result => {
    const text = result.candidates[0].content.parts[0].text;
    console.log('Response:', text);
  })
  .catch(e => console.error(e));
```

### Admin Panel Testing

1. **Navigate to Admin Panel:**
   - URL: `https://emailapi.6ray.com/admin/aiconfig`
   - Enter panel password

2. **Configure Gemini:**
   - Paste API key from Google AI Studio
   - Click **Test Gemini API Key**
   - Verify success message shows API response

3. **Save Configuration:**
   - Click **Save Gemini API Key**
   - Verify success message

4. **Test Endpoint:**
   - Use curl or browser to fetch `/ai/apikey`
   - Verify API key is returned

---

## Usage Monitoring

### Check Usage in Google AI Studio

1. Visit [Google AI Studio](https://aistudio.google.com/)
2. Go to "API Keys" section
3. Click on your API key
4. View usage statistics:
   - Requests per minute
   - Tokens consumed
   - Daily request count

### Monitor Rate Limits

```javascript
async function checkRateLimit(apiKey) {
  try {
    // Make a test request and check headers
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: 'test' }] }]
        })
      }
    );
    
    // Check response headers for rate limit info
    const remaining = response.headers.get('x-ratelimit-remaining');
    const limit = response.headers.get('x-ratelimit-limit');
    
    console.log(`Rate limit: ${remaining}/${limit} requests remaining`);
    
    return { remaining, limit };
  } catch (error) {
    console.error('Failed to check rate limit:', error);
  }
}
```

---

## Support & Resources

### Documentation

- **Gemini API Documentation:** https://ai.google.dev/docs
- **Google AI Studio:** https://aistudio.google.com/
- **Model List:** https://ai.google.dev/models/gemini
- **Rate Limits:** https://ai.google.dev/pricing

### Admin Panel

- **Configuration:** `https://emailapi.6ray.com/admin/aiconfig`
- **Email Config:** `https://emailapi.6ray.com/admin/config`

### Troubleshooting

1. **Key not working**: Check key validity in Google AI Studio
2. **CORS errors**: Verify domain is in allowed origins
3. **404 errors**: Use valid model name (gemini-2.5-flash)
4. **503 errors**: Configure Gemini API key in admin panel
5. **429 errors**: Wait for rate limit reset or upgrade plan

### Contact

For issues or questions:
- Check admin panel configuration first
- Verify CORS settings for your domain
- Test with curl to isolate client-side issues
- Check API key validity in Google AI Studio

---

**Last Updated:** November 3, 2025
