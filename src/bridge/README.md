# @klangk/bridge

Browser-delegated tool calls for Klangk Pi extensions.

Routes requests through the Klangk backend to the user's browser, which executes them with its session credentials (cookies, OAuth tokens, etc.).

## Usage

```typescript
import { browserFetch, browserAction, isBridgeAvailable } from "@klangk/bridge";

// Fetch a URL using the browser's credentials
const result = await browserFetch("https://authenticated-api.com/data");
console.log(result.status, result.body);

// Trigger a browser-side action
await browserAction("celebrate");
await browserAction("beep");

// Check if the bridge is available
if (await isBridgeAvailable()) {
  // safe to use bridge functions
}
```

## Environment Variables

Set automatically by the Klangk container entrypoint:

- `KLANGK_BRIDGE_URL` — URL of the Klangk backend (via nginx)
- `KLANGK_BRIDGE_TOKEN` — Opaque token that identifies this container's workspace
