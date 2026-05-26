/**
 * @bark/bridge — Browser-delegated tool calls for Bark Pi extensions.
 *
 * Routes requests through the Bark backend to the user's browser,
 * which executes them with its session credentials (cookies, OAuth tokens, etc.).
 */

const BRIDGE_URL = process.env.BARK_BRIDGE_URL;
const WORKSPACE_ID = process.env.BARK_WORKSPACE_ID;

function getConfig() {
  if (!BRIDGE_URL) {
    throw new Error(
      "@bark/bridge: BARK_BRIDGE_URL is not set. " +
        "Are you running inside a Bark container?",
    );
  }
  if (!WORKSPACE_ID) {
    throw new Error(
      "@bark/bridge: BARK_WORKSPACE_ID is not set. " +
        "Are you running inside a Bark container?",
    );
  }
  return { bridgeUrl: `${BRIDGE_URL}/api/browser-delegate`, WORKSPACE_ID };
}

/**
 * Fetch a URL using the user's browser session credentials.
 *
 * @param {string} url - The URL to fetch
 * @param {Object} [options] - Fetch options
 * @param {string} [options.method="GET"] - HTTP method
 * @param {Record<string, string>} [options.headers] - Request headers
 * @param {string} [options.body] - Request body
 * @returns {Promise<{status: number, headers: Record<string, string>, body: string}>}
 */
async function browserFetch(url, options = {}) {
  const { bridgeUrl, WORKSPACE_ID: wsId } = getConfig();

  const resp = await fetch(bridgeUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: "fetch",
      workspace_id: wsId,
      url,
      method: options.method || "GET",
      headers: options.headers || {},
      body: options.body || null,
    }),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(
      `@bark/bridge: fetch request failed (${resp.status}): ${text}`,
    );
  }

  return await resp.json();
}

/**
 * Trigger a browser-side action (e.g. celebrate, beep).
 *
 * @param {string} action - The action name
 * @param {Object} [payload] - Additional action-specific data
 * @returns {Promise<{status: string}>}
 */
async function browserAction(action, payload = {}) {
  const { bridgeUrl, WORKSPACE_ID: wsId } = getConfig();

  const resp = await fetch(bridgeUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action,
      workspace_id: wsId,
      ...payload,
    }),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(
      `@bark/bridge: action '${action}' failed (${resp.status}): ${text}`,
    );
  }

  return await resp.json();
}

/**
 * Check whether the browser bridge is available.
 * @returns {Promise<boolean>}
 */
async function isBridgeAvailable() {
  if (!BRIDGE_URL || !WORKSPACE_ID) return false;
  try {
    const resp = await fetch(`${BRIDGE_URL}/health`, {
      signal: AbortSignal.timeout(2000),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

module.exports = { browserFetch, browserAction, isBridgeAvailable };
