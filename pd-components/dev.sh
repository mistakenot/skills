#!/usr/bin/env bash
# Starts the pd-components dev server and registers it with tailscale serve.
# Run from the repo root via: make pd-dev
# Or directly: bash pd-components/dev.sh

set -euo pipefail

LOCAL_PORT=9173
TAILSCALE_PORT=8743

# Remove the tailscale entry on exit (Ctrl+C or error)
cleanup() {
  echo ""
  echo "Removing tailscale serve on port $TAILSCALE_PORT..."
  tailscale serve --https=$TAILSCALE_PORT off 2>/dev/null || true
}
trap cleanup EXIT

echo "Registering with tailscale serve..."
tailscale serve --bg --https=$TAILSCALE_PORT http://localhost:$LOCAL_PORT
echo "  tailscale URL: $(tailscale serve status 2>/dev/null | grep ":$TAILSCALE_PORT" | awk '{print $1}' | head -1)"
echo ""

cd "$(dirname "$0")"
node dev.mjs
