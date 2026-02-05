/**
 * PaddiSense Registration Worker
 *
 * Cloudflare Worker that handles registration requests from PaddiSense integrations.
 *
 * Features:
 * - Email validation
 * - Registration token generation
 * - Audit logging to GitHub Gist
 * - Registration status checks (for revocation)
 * - Welcome email via Resend (optional)
 *
 * Environment Variables (set in Cloudflare dashboard):
 * - GITHUB_TOKEN: Personal access token with gist scope
 * - GIST_ID: ID of the private gist for storing registrations
 * - RESEND_API_KEY: (Optional) Resend.com API key for welcome emails
 * - ADMIN_EMAIL: Your email for notifications
 * - WORKER_SECRET: Secret key for signing tokens
 */

// CORS headers for cross-origin requests
const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json',
};

// Email validation regex
const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    try {
      // Route requests
      if (request.method === 'POST' && url.pathname === '/register') {
        return await handleRegistration(request, env);
      }

      if (request.method === 'GET' && url.pathname === '/status') {
        return await handleStatusCheck(request, env);
      }

      if (request.method === 'GET' && url.pathname === '/health') {
        return jsonResponse({ status: 'ok', timestamp: new Date().toISOString() });
      }

      // Admin endpoints (protected)
      if (url.pathname === '/admin/registrations') {
        return await handleAdminList(request, env);
      }

      if (url.pathname === '/admin/revoke') {
        return await handleAdminRevoke(request, env);
      }

      return jsonResponse({ error: 'Not found' }, 404);

    } catch (error) {
      console.error('Worker error:', error);
      return jsonResponse({ error: 'Internal server error', error_code: 'server_error' }, 500);
    }
  },
};

/**
 * Handle new registration requests
 */
async function handleRegistration(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: 'Invalid JSON', error_code: 'invalid_request' }, 400);
  }

  const { server_id, grower_name, grower_email, tos_version, timestamp } = body;

  // Validate required fields
  if (!server_id || !grower_name || !grower_email) {
    return jsonResponse({
      error: 'Missing required fields: server_id, grower_name, grower_email',
      error_code: 'invalid_request',
    }, 400);
  }

  // Validate email format
  if (!EMAIL_REGEX.test(grower_email)) {
    return jsonResponse({
      error: 'Invalid email address format',
      error_code: 'invalid_email',
    }, 400);
  }

  // Generate registration token
  const token = await generateToken(server_id, grower_email, env.WORKER_SECRET);

  // Create registration record
  const registration = {
    server_id,
    grower_name,
    grower_email: grower_email.toLowerCase(),
    tos_version: tos_version || '1.0',
    registered_at: new Date().toISOString(),
    token_hash: await hashToken(token),
    ip_address: request.headers.get('CF-Connecting-IP') || 'unknown',
    country: request.headers.get('CF-IPCountry') || 'unknown',
    revoked: false,
    updates_allowed: true,
  };

  // Save to GitHub Gist
  const saveResult = await saveRegistration(registration, env);
  if (!saveResult.success) {
    console.error('Failed to save registration:', saveResult.error);
    // Still return success to user - we can reconcile later
  }

  // Send welcome email (non-blocking)
  if (env.RESEND_API_KEY) {
    ctx.waitUntil(sendWelcomeEmail(grower_name, grower_email, env));
  }

  // Notify admin (non-blocking)
  if (env.ADMIN_EMAIL && env.RESEND_API_KEY) {
    ctx.waitUntil(notifyAdmin(registration, env));
  }

  return jsonResponse({
    success: true,
    token,
    server_id,
    registered_at: registration.registered_at,
    message: 'Registration successful! Welcome to PaddiSense.',
  });
}

/**
 * Handle registration status checks
 */
async function handleStatusCheck(request, env) {
  const url = new URL(request.url);
  const server_id = url.searchParams.get('server_id');
  const token = url.searchParams.get('token');

  if (!server_id) {
    return jsonResponse({ error: 'Missing server_id', error_code: 'invalid_request' }, 400);
  }

  // Load registrations from Gist
  const registrations = await loadRegistrations(env);
  const registration = registrations[server_id];

  if (!registration) {
    return jsonResponse({
      valid: false,
      reason: 'not_registered',
    });
  }

  // Verify token if provided
  if (token) {
    const expectedHash = await hashToken(token);
    if (registration.token_hash !== expectedHash) {
      return jsonResponse({
        valid: false,
        reason: 'invalid_token',
      });
    }
  }

  return jsonResponse({
    valid: !registration.revoked,
    revoked: registration.revoked || false,
    updates_allowed: registration.updates_allowed !== false,
    registered_at: registration.registered_at,
    message: registration.revoked ? 'This registration has been revoked.' : null,
  });
}

/**
 * Admin: List all registrations
 */
async function handleAdminList(request, env) {
  // Simple auth check - require admin token in header
  const authHeader = request.headers.get('Authorization');
  if (!authHeader || authHeader !== `Bearer ${env.ADMIN_TOKEN}`) {
    return jsonResponse({ error: 'Unauthorized' }, 401);
  }

  const registrations = await loadRegistrations(env);

  // Return summary (hide sensitive data)
  const summary = Object.entries(registrations).map(([id, reg]) => ({
    server_id: id,
    grower_name: reg.grower_name,
    grower_email: reg.grower_email,
    registered_at: reg.registered_at,
    country: reg.country,
    revoked: reg.revoked || false,
    updates_allowed: reg.updates_allowed !== false,
  }));

  return jsonResponse({
    total: summary.length,
    registrations: summary,
  });
}

/**
 * Admin: Revoke a registration
 */
async function handleAdminRevoke(request, env) {
  // Simple auth check
  const authHeader = request.headers.get('Authorization');
  if (!authHeader || authHeader !== `Bearer ${env.ADMIN_TOKEN}`) {
    return jsonResponse({ error: 'Unauthorized' }, 401);
  }

  if (request.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed' }, 405);
  }

  const body = await request.json();
  const { server_id, revoke_updates_only } = body;

  if (!server_id) {
    return jsonResponse({ error: 'Missing server_id' }, 400);
  }

  const registrations = await loadRegistrations(env);

  if (!registrations[server_id]) {
    return jsonResponse({ error: 'Registration not found' }, 404);
  }

  if (revoke_updates_only) {
    registrations[server_id].updates_allowed = false;
  } else {
    registrations[server_id].revoked = true;
    registrations[server_id].updates_allowed = false;
  }
  registrations[server_id].revoked_at = new Date().toISOString();

  await saveRegistrationsToGist(registrations, env);

  return jsonResponse({
    success: true,
    message: revoke_updates_only
      ? 'Updates revoked for this registration'
      : 'Registration fully revoked',
  });
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Generate a registration token
 */
async function generateToken(server_id, email, secret) {
  const data = `${server_id}:${email.toLowerCase()}:${Date.now()}`;
  const encoder = new TextEncoder();

  // Use HMAC-SHA256 for token generation
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret || 'default-secret-change-me'),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const signature = await crypto.subtle.sign('HMAC', key, encoder.encode(data));
  const hashArray = Array.from(new Uint8Array(signature));
  const token = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

  return `ps_${token.substring(0, 32)}`;
}

/**
 * Hash a token for storage (don't store raw tokens)
 */
async function hashToken(token) {
  const encoder = new TextEncoder();
  const data = encoder.encode(token);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Load registrations from GitHub Gist
 */
async function loadRegistrations(env) {
  if (!env.GITHUB_TOKEN || !env.GIST_ID) {
    console.warn('GitHub credentials not configured, using empty registrations');
    return {};
  }

  try {
    const response = await fetch(`https://api.github.com/gists/${env.GIST_ID}`, {
      headers: {
        'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
        'User-Agent': 'PaddiSense-Worker',
        'Accept': 'application/vnd.github+json',
      },
    });

    if (!response.ok) {
      console.error('Failed to load gist:', response.status);
      return {};
    }

    const gist = await response.json();
    const content = gist.files['registrations.json']?.content;

    if (!content) {
      return {};
    }

    return JSON.parse(content);
  } catch (error) {
    console.error('Error loading registrations:', error);
    return {};
  }
}

/**
 * Save a single registration to GitHub Gist
 */
async function saveRegistration(registration, env) {
  if (!env.GITHUB_TOKEN || !env.GIST_ID) {
    console.warn('GitHub credentials not configured, skipping save');
    return { success: false, error: 'Not configured' };
  }

  try {
    // Load existing registrations
    const registrations = await loadRegistrations(env);

    // Add/update this registration
    registrations[registration.server_id] = registration;

    // Save back to Gist
    return await saveRegistrationsToGist(registrations, env);
  } catch (error) {
    console.error('Error saving registration:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Save all registrations to GitHub Gist
 */
async function saveRegistrationsToGist(registrations, env) {
  try {
    const response = await fetch(`https://api.github.com/gists/${env.GIST_ID}`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
        'User-Agent': 'PaddiSense-Worker',
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        files: {
          'registrations.json': {
            content: JSON.stringify(registrations, null, 2),
          },
        },
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      console.error('Failed to update gist:', error);
      return { success: false, error };
    }

    return { success: true };
  } catch (error) {
    console.error('Error updating gist:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Send welcome email via Resend
 */
async function sendWelcomeEmail(name, email, env) {
  if (!env.RESEND_API_KEY) return;

  try {
    await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'PaddiSense <noreply@paddisense.com>',
        to: email,
        subject: 'Welcome to PaddiSense!',
        html: `
          <h1>Welcome to PaddiSense, ${name}!</h1>
          <p>Your registration is complete. You now have access to all free modules:</p>
          <ul>
            <li><strong>IPM</strong> - Inventory Manager</li>
            <li><strong>ASM</strong> - Asset Service Manager</li>
            <li><strong>Weather</strong> - Weather Stations</li>
            <li><strong>PWM</strong> - Water Management</li>
            <li><strong>RTR</strong> - Real Time Rice</li>
            <li><strong>STR</strong> - Stock Tracker</li>
            <li><strong>WSS</strong> - Worker Safety</li>
          </ul>
          <p>Use the <strong>PaddiSense Manager</strong> dashboard in Home Assistant to:</p>
          <ul>
            <li>Add your farms and paddocks</li>
            <li>Install modules</li>
            <li>Manage seasons</li>
          </ul>
          <p>Need help? Reply to this email or visit our documentation.</p>
          <p>Happy farming!<br>The PaddiSense Team</p>
        `,
      }),
    });
  } catch (error) {
    console.error('Failed to send welcome email:', error);
  }
}

/**
 * Notify admin of new registration
 */
async function notifyAdmin(registration, env) {
  if (!env.RESEND_API_KEY || !env.ADMIN_EMAIL) return;

  try {
    await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${env.RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'PaddiSense <noreply@paddisense.com>',
        to: env.ADMIN_EMAIL,
        subject: `New PaddiSense Registration: ${registration.grower_name}`,
        html: `
          <h2>New Registration</h2>
          <table>
            <tr><td><strong>Name:</strong></td><td>${registration.grower_name}</td></tr>
            <tr><td><strong>Email:</strong></td><td>${registration.grower_email}</td></tr>
            <tr><td><strong>Server ID:</strong></td><td>${registration.server_id}</td></tr>
            <tr><td><strong>Country:</strong></td><td>${registration.country}</td></tr>
            <tr><td><strong>Time:</strong></td><td>${registration.registered_at}</td></tr>
          </table>
        `,
      }),
    });
  } catch (error) {
    console.error('Failed to notify admin:', error);
  }
}

/**
 * JSON response helper
 */
function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: CORS_HEADERS,
  });
}
