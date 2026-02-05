# PaddiSense Registration Worker

Cloudflare Worker that handles registration requests from PaddiSense integrations.

## Features

- **Instant registration** - No waiting for approval
- **Email validation** - Verifies email format
- **GitHub audit log** - All registrations stored in a private Gist
- **Welcome emails** - Optional via Resend.com
- **Admin notifications** - Get notified of new registrations
- **Revocation support** - Can revoke access to updates

## Setup Guide

### Step 1: Create a GitHub Gist

1. Go to https://gist.github.com
2. Create a **Secret** gist (not public)
3. Filename: `registrations.json`
4. Content: `{}`
5. Save and copy the Gist ID from the URL (e.g., `abc123def456`)

### Step 2: Create a GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scope: `gist`
4. Generate and copy the token

### Step 3: Create the Cloudflare Worker

1. Go to https://dash.cloudflare.com
2. Navigate to **Workers & Pages**
3. Click **Create Application** → **Create Worker**
4. Name it: `paddisense-registration`
5. Click **Deploy**

### Step 4: Add the Code

1. Click **Edit code**
2. Replace the default code with the contents of `worker.js`
3. Click **Save and Deploy**

### Step 5: Configure Environment Variables

1. Go to your Worker → **Settings** → **Variables**
2. Add these **Environment Variables**:

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub personal access token with `gist` scope | Yes |
| `GIST_ID` | ID of your private gist | Yes |
| `WORKER_SECRET` | Random string for signing tokens (generate one) | Yes |
| `ADMIN_TOKEN` | Secret for admin API access | Yes |
| `RESEND_API_KEY` | Resend.com API key for emails | Optional |
| `ADMIN_EMAIL` | Your email for notifications | Optional |

**To generate secrets:**
```bash
# Generate WORKER_SECRET
openssl rand -hex 32

# Generate ADMIN_TOKEN
openssl rand -hex 32
```

### Step 6: (Optional) Set Up Email with Resend

1. Sign up at https://resend.com (free tier: 3,000 emails/month)
2. Add and verify your domain
3. Create an API key
4. Add it as `RESEND_API_KEY` environment variable

### Step 7: Configure Custom Domain (Optional)

1. Go to your Worker → **Settings** → **Triggers**
2. Add a custom domain (e.g., `api.paddisense.com`)

### Step 8: Update PaddiSense Integration

In `/config/custom_components/paddisense/const.py`, update:

```python
REGISTRATION_ENDPOINT = "https://paddisense-registration.YOUR-SUBDOMAIN.workers.dev/register"
```

Or with custom domain:
```python
REGISTRATION_ENDPOINT = "https://api.paddisense.com/register"
```

## API Endpoints

### POST /register

Register a new PaddiSense server.

**Request:**
```json
{
  "server_id": "ps-abc123",
  "grower_name": "John Smith",
  "grower_email": "john@example.com",
  "tos_version": "1.0",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Response (200):**
```json
{
  "success": true,
  "token": "ps_abc123def456...",
  "server_id": "ps-abc123",
  "registered_at": "2024-01-15T10:30:00Z",
  "message": "Registration successful! Welcome to PaddiSense."
}
```

**Response (400 - Invalid Email):**
```json
{
  "error": "Invalid email address format",
  "error_code": "invalid_email"
}
```

### GET /status

Check registration status.

**Request:**
```
GET /status?server_id=ps-abc123&token=ps_abc123def456...
```

**Response:**
```json
{
  "valid": true,
  "revoked": false,
  "updates_allowed": true,
  "registered_at": "2024-01-15T10:30:00Z"
}
```

### GET /health

Health check endpoint.

```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### GET /admin/registrations (Protected)

List all registrations. Requires `Authorization: Bearer {ADMIN_TOKEN}` header.

### POST /admin/revoke (Protected)

Revoke a registration. Requires `Authorization: Bearer {ADMIN_TOKEN}` header.

**Request:**
```json
{
  "server_id": "ps-abc123",
  "revoke_updates_only": true  // or false for full revocation
}
```

## Managing Registrations

### View All Registrations

```bash
curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  https://your-worker.workers.dev/admin/registrations
```

### Revoke Updates Only

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"server_id": "ps-abc123", "revoke_updates_only": true}' \
  https://your-worker.workers.dev/admin/revoke
```

### Full Revocation

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"server_id": "ps-abc123", "revoke_updates_only": false}' \
  https://your-worker.workers.dev/admin/revoke
```

## Cost

**Cloudflare Workers Free Tier:**
- 100,000 requests/day
- No credit card required

**Resend Free Tier:**
- 3,000 emails/month
- 100 emails/day

**GitHub Gist:**
- Free (unlimited private gists)

## Monitoring

1. **Cloudflare Dashboard** - View request logs, errors, and analytics
2. **GitHub Gist** - Direct access to registration data
3. **Email notifications** - Get notified of each new registration

## Troubleshooting

### "Registration failed" error

1. Check Worker logs in Cloudflare dashboard
2. Verify GITHUB_TOKEN has `gist` scope
3. Verify GIST_ID is correct
4. Test with `/health` endpoint

### Emails not sending

1. Verify domain is configured in Resend
2. Check RESEND_API_KEY is correct
3. Check Resend dashboard for delivery status

### Admin API returns 401

1. Verify ADMIN_TOKEN environment variable is set
2. Ensure header format is `Authorization: Bearer YOUR_TOKEN`
