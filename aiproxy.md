# AI Proxy Service Documentation

## Overview

The AI Proxy Service is a server-side proxy that hides AI provider API keys and allows websites and applications to make AI API calls securely without exposing credentials to clients.

**Key Benefits:**
- 🔐 **Security**: API keys stay server-side, never exposed to clients
- 🌐 **Public Access**: No authentication required for clients (configurable via CORS)
- 🔄 **Multi-Provider**: Support for OpenAI, Anthropic, Google AI, DeepSeek, and custom endpoints
- 🎯 **Simple API**: Single unified endpoint for all AI providers
- 🚀 **Zero Setup**: Just call the API - no client-side configuration needed

## API Endpoint

```
POST https://emailapi.6ray.com/ai/chat
```

**Authentication:** None required (public endpoint, controlled by CORS)

## Request Format

### Basic Request

```json
{
  "messages": [
    {"role": "user", "content": "Your question here"}
  ]
}
```

### Advanced Request (Optional Parameters)

```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Your question here"}
  ],
  "model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `messages` | Array | **Yes** | Array of message objects with `role` and `content` |
| `model` | String | No | AI model to use (uses provider default if omitted) |
| `temperature` | Float | No | Randomness (0.0-2.0). Higher = more creative |
| `max_tokens` | Integer | No | Maximum response length |

### Message Roles

- `system`: Sets behavior/context for the AI (optional)
- `user`: Your message/question to the AI
- `assistant`: Previous AI responses (for conversation history)

## Response Format

### Success Response

```json
{
  "success": true,
  "response": {
    "id": "chatcmpl-...",
    "choices": [
      {
        "message": {
          "role": "assistant",
          "content": "AI response here"
        },
        "finish_reason": "stop"
      }
    ],
    "model": "gpt-3.5-turbo",
    "usage": {
      "prompt_tokens": 10,
      "completion_tokens": 20,
      "total_tokens": 30
    }
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": "Error description"
}
```

**Note:** Response format varies by AI provider (OpenAI, Anthropic, Google, DeepSeek). Extract content appropriately based on provider structure.

## Usage Examples

### cURL

```bash
curl -X POST https://emailapi.6ray.com/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is 5+7?"}
    ]
  }'
```

### JavaScript (Fetch API)

```javascript
async function askAI(question) {
  const response = await fetch('https://emailapi.6ray.com/ai/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      messages: [
        { role: 'user', content: question }
      ]
    })
  });
  
  const data = await response.json();
  
  // Extract content based on provider
  if (data.success && data.response.choices) {
    // OpenAI/DeepSeek format
    return data.response.choices[0].message.content;
  } else if (data.success && data.response.content) {
    // Anthropic format
    return data.response.content[0].text;
  } else if (data.success && data.response.candidates) {
    // Google format
    return data.response.candidates[0].content.parts[0].text;
  }
  
  throw new Error(data.error || 'Unknown error');
}

// Usage
askAI('What is the capital of France?')
  .then(answer => console.log(answer))
  .catch(error => console.error(error));
```

### JavaScript (Axios)

```javascript
import axios from 'axios';

async function chatWithAI(messages) {
  try {
    const response = await axios.post('https://emailapi.6ray.com/ai/chat', {
      messages: messages,
      temperature: 0.7,
      max_tokens: 500
    });
    
    return response.data;
  } catch (error) {
    console.error('AI Error:', error.response?.data || error.message);
    throw error;
  }
}

// Usage
chatWithAI([
  { role: 'system', content: 'You are a math tutor.' },
  { role: 'user', content: 'Explain Pythagorean theorem' }
]).then(data => console.log(data));
```

### Python (requests)

```python
import requests

def ask_ai(question, model=None):
    url = "https://emailapi.6ray.com/ai/chat"
    
    payload = {
        "messages": [
            {"role": "user", "content": question}
        ]
    }
    
    if model:
        payload["model"] = model
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    
    data = response.json()
    
    if data["success"]:
        # Extract content based on provider format
        resp = data["response"]
        if "choices" in resp:
            # OpenAI/DeepSeek format
            return resp["choices"][0]["message"]["content"]
        elif "content" in resp:
            # Anthropic format
            return resp["content"][0]["text"]
        elif "candidates" in resp:
            # Google format
            return resp["candidates"][0]["content"]["parts"][0]["text"]
    
    raise Exception(data.get("error", "Unknown error"))

# Usage
answer = ask_ai("What is 5+7?")
print(answer)
```

### React Hook

```javascript
import { useState } from 'react';

function useAIChat() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const chat = async (messages) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('https://emailapi.6ray.com/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages })
      });
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error);
      }
      
      setLoading(false);
      return data.response;
    } catch (err) {
      setError(err.message);
      setLoading(false);
      throw err;
    }
  };

  return { chat, loading, error };
}

// Usage in component
function ChatComponent() {
  const { chat, loading, error } = useAIChat();
  const [answer, setAnswer] = useState('');

  const handleAsk = async () => {
    try {
      const response = await chat([
        { role: 'user', content: 'Hello!' }
      ]);
      setAnswer(response.choices[0].message.content);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div>
      <button onClick={handleAsk} disabled={loading}>
        {loading ? 'Asking...' : 'Ask AI'}
      </button>
      {error && <p>Error: {error}</p>}
      {answer && <p>Answer: {answer}</p>}
    </div>
  );
}
```

## Conversation Context

To maintain conversation history, include previous messages:

```javascript
const conversation = [
  { role: 'user', content: 'What is 5+7?' },
  { role: 'assistant', content: '5+7 equals 12.' },
  { role: 'user', content: 'What about 5+8?' }
];

fetch('https://emailapi.6ray.com/ai/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ messages: conversation })
});
```

## Supported AI Providers

The proxy currently supports the following AI providers (configured by admin):

### OpenAI
- **Models**: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`, etc.
- **Response Format**: Standard OpenAI format with `choices` array

### Anthropic (Claude)
- **Models**: `claude-3-opus`, `claude-3-sonnet`, `claude-2`, etc.
- **Response Format**: Anthropic format with `content` array
- **Note**: `max_tokens` parameter is required for Claude

### Google AI (Gemini)
- **Models**: `gemini-pro`, `gemini-pro-vision`, etc.
- **Response Format**: Google format with `candidates` array

### DeepSeek
- **Models**: `deepseek-chat` (non-thinking), `deepseek-reasoner` (thinking mode)
- **Response Format**: OpenAI-compatible format
- **Note**: DeepSeek-V3.2-Exp models

### Custom Endpoints
- Any OpenAI-compatible API endpoint
- Same request/response format as OpenAI

## CORS Configuration

The API uses Cross-Origin Resource Sharing (CORS) to control which websites can access the proxy.

**Current configuration is managed by the admin at:**
`https://emailapi.6ray.com/admin/aiconfig`

### Typical CORS Settings

- `*` - Allow all origins (public)
- `https://yourdomain.com` - Specific domain only
- `https://*.yourdomain.com` - All subdomains (e.g., api.yourdomain.com, app.yourdomain.com)
- `http://localhost:3000` - Local development

**If you receive CORS errors**, contact your administrator to add your domain to the allowed origins list.

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 503 Service Unavailable | No AI provider configured | Admin must enable a provider |
| CORS Error | Origin not allowed | Request domain whitelist from admin |
| 400 Bad Request | Invalid request format | Check request JSON structure |
| 500 Internal Server Error | Provider API issue | Check provider status or contact admin |
| Timeout | Request took too long | Provider may be slow, retry or use shorter prompt |

### Error Handling Example

```javascript
async function safeAICall(messages) {
  try {
    const response = await fetch('https://emailapi.6ray.com/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'AI request failed');
    }
    
    return data.response;
  } catch (error) {
    console.error('AI Error:', error);
    
    if (error.name === 'TypeError') {
      return { error: 'Network error - check connection' };
    } else if (error.message.includes('503')) {
      return { error: 'AI service not configured' };
    }
    
    return { error: error.message };
  }
}
```

## Best Practices

### 1. Handle Responses Properly

Different providers return different response formats. Always check the structure:

```javascript
function extractContent(apiResponse) {
  if (!apiResponse.success) {
    throw new Error(apiResponse.error);
  }
  
  const resp = apiResponse.response;
  
  // OpenAI/DeepSeek
  if (resp.choices?.[0]?.message?.content) {
    return resp.choices[0].message.content;
  }
  
  // Anthropic
  if (resp.content?.[0]?.text) {
    return resp.content[0].text;
  }
  
  // Google
  if (resp.candidates?.[0]?.content?.parts?.[0]?.text) {
    return resp.candidates[0].content.parts[0].text;
  }
  
  throw new Error('Unknown response format');
}
```

### 2. Implement Timeouts

AI requests can take time. Set appropriate timeouts:

```javascript
const controller = new AbortController();
const timeout = setTimeout(() => controller.abort(), 30000); // 30s timeout

fetch('https://emailapi.6ray.com/ai/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ messages }),
  signal: controller.signal
}).finally(() => clearTimeout(timeout));
```

### 3. Add Loading States

```javascript
const [isLoading, setIsLoading] = useState(false);

async function askQuestion() {
  setIsLoading(true);
  try {
    const response = await fetch('https://emailapi.6ray.com/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content: question }]
      })
    });
    const data = await response.json();
    // Handle response...
  } finally {
    setIsLoading(false);
  }
}
```

### 4. Rate Limiting

Consider implementing client-side rate limiting to avoid overwhelming the service:

```javascript
class RateLimiter {
  constructor(maxRequests, perSeconds) {
    this.maxRequests = maxRequests;
    this.perSeconds = perSeconds;
    this.requests = [];
  }
  
  async throttle() {
    const now = Date.now();
    this.requests = this.requests.filter(
      time => now - time < this.perSeconds * 1000
    );
    
    if (this.requests.length >= this.maxRequests) {
      const oldestRequest = Math.min(...this.requests);
      const waitTime = (oldestRequest + this.perSeconds * 1000) - now;
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
    
    this.requests.push(now);
  }
}

const limiter = new RateLimiter(10, 60); // 10 requests per 60 seconds

async function rateLimitedAICall(messages) {
  await limiter.throttle();
  return fetch('https://emailapi.6ray.com/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages })
  });
}
```

## Testing

Test the API endpoint to verify it's working:

```bash
# Simple test
curl -X POST https://emailapi.6ray.com/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say hello!"}]}'

# With model specification
curl -X POST https://emailapi.6ray.com/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role":"user","content":"What is 2+2?"}],
    "model": "gpt-3.5-turbo",
    "temperature": 0.5
  }'
```

## Admin Configuration

**For administrators only:**

Access the AI proxy admin panel at `https://emailapi.6ray.com/admin/aiconfig` (password protected).

**Configuration options:**
- Add/remove AI providers (OpenAI, Anthropic, Google, DeepSeek, Custom)
- Enable/disable providers (only one active at a time)
- Configure CORS allowed origins
- Test the proxy with built-in test button
- View current provider status

## Support

**Issues or Questions?**
- Contact your system administrator
- Check admin panel status: `https://emailapi.6ray.com/admin/aiconfig`
- Verify CORS configuration for your domain
- Test with cURL to rule out client-side issues

## License

This service is provided as-is. Contact your organization for usage policies and limitations.
