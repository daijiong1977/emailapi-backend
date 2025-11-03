# GitHub Token Proxy API

## Overview

The GitHub Token Proxy provides secure, session-based access to GitHub repositories without storing credentials in client applications. The proxy returns GitHub configuration and access tokens to authorized domains via CORS protection.

**Base URL:** `https://emailapi.6ray.com`

**Key Features:**
- 🔐 **Session-Based Security**: Tokens fetched per session, no local storage
- 🌐 **Cross-Device**: Works on any browser/device without configuration
- 🎯 **CORS Protected**: Only authorized domains can access tokens
- 🚀 **Zero Persistence**: Never stored in localStorage or cookies
- ✅ **Easy Admin**: Configure via web panel at `/admin/aiconfig`

---

## API Endpoints

### Get GitHub Token and Configuration

Retrieve GitHub access token and repository configuration for authorized clients.

**Endpoint:** `GET /github/token`

**Authentication:** None required (controlled by CORS)

**Request:**

```bash
curl https://emailapi.6ray.com/github/token
```

**Success Response (200 OK):**

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

**Error Response (503 Service Unavailable):**

```json
{
  "detail": "GitHub token not configured"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Operation success status |
| `token` | string | GitHub personal access token |
| `config.owner` | string | Repository owner (username or org) |
| `config.repo` | string | Repository name |
| `config.branch` | string | Branch name (default: main) |
| `config.basePath` | string | Base directory path in repo |

---

## Client Implementation

### JavaScript/TypeScript Example

```typescript
// Fetch GitHub configuration on app startup
async function loadGitHubConfig() {
  try {
    const response = await fetch('https://emailapi.6ray.com/github/token');
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (data.success) {
      // Store in memory for session
      window.githubConfig = {
        owner: data.config.owner,
        repo: data.config.repo,
        branch: data.config.branch,
        basePath: data.config.basePath,
        token: data.token
      };
      
      console.log(`Connected to ${data.config.owner}/${data.config.repo}`);
      return window.githubConfig;
    }
  } catch (error) {
    console.error('Failed to load GitHub config:', error);
    throw error;
  }
}

// Use token to access GitHub API
async function saveToGitHub(filename, content) {
  const config = window.githubConfig;
  const path = `${config.basePath}/${filename}`;
  
  const response = await fetch(
    `https://api.github.com/repos/${config.owner}/${config.repo}/contents/${path}`,
    {
      method: 'PUT',
      headers: {
        'Authorization': `token ${config.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: `Save ${filename}`,
        content: btoa(content), // Base64 encode
        branch: config.branch
      })
    }
  );
  
  return response.json();
}

// Initialize on page load
loadGitHubConfig().then(() => {
  console.log('GitHub ready!');
}).catch(err => {
  console.error('GitHub initialization failed:', err);
});
```

### React Example

```typescript
import { useEffect, useState } from 'react';

interface GitHubConfig {
  owner: string;
  repo: string;
  branch: string;
  basePath: string;
  token: string;
}

export function useGitHub() {
  const [config, setConfig] = useState<GitHubConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('https://emailapi.6ray.com/github/token')
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch GitHub config');
        return res.json();
      })
      .then(data => {
        if (data.success) {
          setConfig({
            owner: data.config.owner,
            repo: data.config.repo,
            branch: data.config.branch,
            basePath: data.config.basePath,
            token: data.token
          });
        }
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return { config, loading, error };
}

// Usage in component
function App() {
  const { config, loading, error } = useGitHub();

  if (loading) return <div>Loading GitHub...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!config) return <div>GitHub not configured</div>;

  return <div>Connected to {config.owner}/{config.repo}</div>;
}
```

### cURL Example

```bash
# Fetch configuration
curl -X GET https://emailapi.6ray.com/github/token

# Use token to list repository contents
TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
curl -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/daijiong1977/swimmeet/contents/public/shares

# Create or update a file
curl -X PUT \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Add new file",
    "content": "SGVsbG8sIFdvcmxkIQ==",
    "branch": "main"
  }' \
  https://api.github.com/repos/daijiong1977/swimmeet/contents/public/shares/test.txt
```

---

## Admin Configuration

### Access Admin Panel

Navigate to: `https://emailapi.6ray.com/admin/aiconfig`

### GitHub Storage Configuration Section

The admin panel includes a dedicated section for GitHub configuration:

**Required Fields:**

1. **GitHub Personal Access Token**
   - Generate at: [github.com/settings/tokens](https://github.com/settings/tokens)
   - Required permissions:
     - `repo` (full control) for private repositories
     - `public_repo` for public repositories only

2. **Repository Owner**
   - GitHub username or organization name
   - Example: `daijiong1977`

3. **Repository Name**
   - Name of the target repository
   - Example: `swimmeet`

4. **Base Path**
   - Base directory path in the repository
   - Example: `public/shares`
   - Files will be created relative to this path

5. **Branch**
   - Target branch name
   - Default: `main`
   - Common alternatives: `master`, `develop`

**Actions:**

- **Test GitHub Connection**: Verifies credentials and displays repository details
- **Save GitHub Configuration**: Saves settings to server (stores in .env file)

---

## CORS Configuration

### Allowed Origins

Configure which domains can access the GitHub token endpoint via the admin panel's CORS settings.

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

### Token Storage

✅ **Server-Side (.env file):**
```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_OWNER=daijiong1977
GITHUB_REPO=swimmeet
GITHUB_BASE_PATH=public/shares
GITHUB_BRANCH=main
```

❌ **Never commit tokens to git:**
- Add `.env` to `.gitignore`
- Use environment variables in production
- Rotate tokens regularly

### Token Permissions

**Minimum Required Permissions:**

For **public repositories**:
- ✅ `public_repo` - Access public repositories

For **private repositories**:
- ✅ `repo` - Full control of private repositories

**Not Required:**
- ❌ User permissions (read:user, user:email, etc.)
- ❌ Delete permissions
- ❌ Admin permissions (repo:admin)
- ❌ Workflow permissions

### CORS Protection

The endpoint has **no authentication** but is protected by CORS:

- Only whitelisted domains can call the endpoint from browsers
- Direct API calls (curl, Postman) always work
- Configure CORS in admin panel to restrict access

### Best Practices

1. **Use Fine-Grained Tokens**: GitHub's new fine-grained tokens allow repo-specific access
2. **Set Token Expiration**: Configure tokens to expire (90 days recommended)
3. **Restrict CORS**: Only allow necessary domains
4. **Monitor Usage**: Check GitHub token usage in repository settings
5. **Rotate Regularly**: Update tokens periodically via admin panel
6. **Use HTTPS Only**: Never send tokens over unencrypted connections

---

## Error Handling

### Common Errors

| Error | Status | Cause | Solution |
|-------|--------|-------|----------|
| GitHub token not configured | 503 | Token not set in admin panel | Configure in admin panel |
| CORS error | - | Origin not whitelisted | Add domain to CORS settings |
| 401 Unauthorized (GitHub API) | 401 | Invalid or expired token | Generate new token |
| 403 Forbidden (GitHub API) | 403 | Insufficient permissions | Add `repo` or `public_repo` scope |
| 404 Not Found (GitHub API) | 404 | Repository or file not found | Check owner/repo/path names |

### Error Response Format

**Server Error (503):**
```json
{
  "detail": "GitHub token not configured"
}
```

**CORS Error (Browser Console):**
```
Access to fetch at 'https://emailapi.6ray.com/github/token' from origin 
'https://example.com' has been blocked by CORS policy
```

**GitHub API Error (401):**
```json
{
  "message": "Bad credentials",
  "documentation_url": "https://docs.github.com/rest"
}
```

### Error Handling Example

```typescript
async function loadGitHubConfig() {
  try {
    const response = await fetch('https://emailapi.6ray.com/github/token');
    
    // Handle HTTP errors
    if (response.status === 503) {
      console.error('GitHub not configured on server');
      return null;
    }
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (!data.success) {
      console.error('Failed to get GitHub config:', data.error);
      return null;
    }
    
    return data;
    
  } catch (error) {
    // Handle network errors, CORS errors, etc.
    if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
      console.error('Network error or CORS blocked. Check CORS settings.');
    } else {
      console.error('Unexpected error:', error);
    }
    return null;
  }
}
```

---

## Testing

### Test Configuration

```bash
# Test endpoint is accessible
curl -I https://emailapi.6ray.com/github/token

# Test with configured token
curl https://emailapi.6ray.com/github/token | jq

# Test GitHub API with returned token
TOKEN=$(curl -s https://emailapi.6ray.com/github/token | jq -r '.token')
curl -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/daijiong1977/swimmeet
```

### Test from Browser Console

```javascript
// Test endpoint access
fetch('https://emailapi.6ray.com/github/token')
  .then(r => r.json())
  .then(d => console.log(d))
  .catch(e => console.error(e));

// Test GitHub API with token
fetch('https://emailapi.6ray.com/github/token')
  .then(r => r.json())
  .then(async data => {
    const repoInfo = await fetch(
      `https://api.github.com/repos/${data.config.owner}/${data.config.repo}`,
      {
        headers: {
          'Authorization': `token ${data.token}`,
          'Accept': 'application/vnd.github.v3+json'
        }
      }
    );
    return repoInfo.json();
  })
  .then(repo => console.log('Repository:', repo.full_name))
  .catch(e => console.error(e));
```

### Admin Panel Testing

1. **Navigate to Admin Panel:**
   - URL: `https://emailapi.6ray.com/admin/aiconfig`
   - Enter panel password

2. **Configure GitHub:**
   - Fill in token, owner, repo, basePath
   - Click **Test GitHub Connection**
   - Verify success message shows repository details

3. **Save Configuration:**
   - Click **Save GitHub Configuration**
   - Verify success message

4. **Test Endpoint:**
   - Use curl or browser to fetch `/github/token`
   - Verify token and config are returned

---

## GitHub API Usage Examples

Once you have the token and config from the proxy, you can use the GitHub REST API:

### List Directory Contents

```javascript
const { token, config } = await fetch('https://emailapi.6ray.com/github/token')
  .then(r => r.json());

const files = await fetch(
  `https://api.github.com/repos/${config.owner}/${config.repo}/contents/${config.basePath}`,
  {
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json'
    }
  }
).then(r => r.json());

console.log('Files:', files.map(f => f.name));
```

### Read File Content

```javascript
const { token, config } = await fetch('https://emailapi.6ray.com/github/token')
  .then(r => r.json());

const file = await fetch(
  `https://api.github.com/repos/${config.owner}/${config.repo}/contents/${config.basePath}/example.json`,
  {
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json'
    }
  }
).then(r => r.json());

// Decode base64 content
const content = atob(file.content);
console.log('File content:', content);
```

### Create or Update File

```javascript
const { token, config } = await fetch('https://emailapi.6ray.com/github/token')
  .then(r => r.json());

const content = JSON.stringify({ name: 'John', age: 30 }, null, 2);

const response = await fetch(
  `https://api.github.com/repos/${config.owner}/${config.repo}/contents/${config.basePath}/data.json`,
  {
    method: 'PUT',
    headers: {
      'Authorization': `token ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'application/vnd.github.v3+json'
    },
    body: JSON.stringify({
      message: 'Create data.json',
      content: btoa(content), // Base64 encode
      branch: config.branch
    })
  }
).then(r => r.json());

console.log('File created:', response.content.html_url);
```

### Delete File

```javascript
const { token, config } = await fetch('https://emailapi.6ray.com/github/token')
  .then(r => r.json());

// First, get the file's SHA
const file = await fetch(
  `https://api.github.com/repos/${config.owner}/${config.repo}/contents/${config.basePath}/data.json`,
  {
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json'
    }
  }
).then(r => r.json());

// Delete the file
const response = await fetch(
  `https://api.github.com/repos/${config.owner}/${config.repo}/contents/${config.basePath}/data.json`,
  {
    method: 'DELETE',
    headers: {
      'Authorization': `token ${token}`,
      'Content-Type': 'application/json',
      'Accept': 'application/vnd.github.v3+json'
    },
    body: JSON.stringify({
      message: 'Delete data.json',
      sha: file.sha,
      branch: config.branch
    })
  }
).then(r => r.json());

console.log('File deleted');
```

---

## Rate Limiting

### GitHub API Limits

**With Authentication:**
- 5,000 requests per hour per token
- Check remaining requests: `X-RateLimit-Remaining` header

**Without Authentication:**
- 60 requests per hour per IP

### Check Rate Limit

```javascript
const { token } = await fetch('https://emailapi.6ray.com/github/token')
  .then(r => r.json());

const rateLimit = await fetch(
  'https://api.github.com/rate_limit',
  {
    headers: {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json'
    }
  }
).then(r => r.json());

console.log('Remaining requests:', rateLimit.resources.core.remaining);
console.log('Reset at:', new Date(rateLimit.resources.core.reset * 1000));
```

---

## Support & Resources

### Documentation

- **GitHub REST API:** https://docs.github.com/rest
- **GitHub Authentication:** https://docs.github.com/rest/overview/authenticating
- **Personal Access Tokens:** https://docs.github.com/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token

### Admin Panel

- **Configuration:** `https://emailapi.6ray.com/admin/aiconfig`
- **Email Config:** `https://emailapi.6ray.com/admin/config`

### Troubleshooting

1. **Token not working**: Check token permissions and expiration
2. **CORS errors**: Verify domain is in allowed origins
3. **404 errors**: Check repository owner/name and file paths
4. **503 errors**: Configure GitHub token in admin panel

### Contact

For issues or questions:
- Check admin panel configuration first
- Verify CORS settings for your domain
- Test with curl to isolate client-side issues
- Check GitHub token permissions and expiration

---

**Last Updated:** November 3, 2025
