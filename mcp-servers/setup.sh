#!/bin/bash
# Setup MCP servers for VidGo
# Run this once before docker build

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 1. Pollo.ai MCP Server (npm package) ──
echo "=== Setting up Pollo.ai MCP Server ==="

if command -v npx &>/dev/null && npx mcp-server-pollo --help &>/dev/null 2>&1; then
  echo "mcp-server-pollo already available via npx"
else
  echo "Installing pollo-mcp globally..."
  npm install -g pollo-mcp
fi

echo "✅ pollo-mcp ready (used at runtime via: npx -y mcp-server-pollo)"
echo "   Requires env: POLLO_API_KEY"
echo ""

# ── 2. PiAPI MCP Server (build from source) ──
echo "=== Setting up PiAPI MCP Server ==="

if [ -d "$SCRIPT_DIR/piapi-mcp-server" ]; then
  echo "piapi-mcp-server already exists, pulling latest..."
  cd "$SCRIPT_DIR/piapi-mcp-server"
  git pull
else
  echo "Cloning piapi-mcp-server..."
  cd "$SCRIPT_DIR"
  git clone https://github.com/apinetwork/piapi-mcp-server.git piapi-mcp-server
fi

echo "Installing dependencies and building..."
cd "$SCRIPT_DIR/piapi-mcp-server"
npm install
npm run build

echo ""
echo "=== Setup Complete ==="
echo "Pollo MCP: installed globally (npx -y mcp-server-pollo)"
echo "PiAPI MCP: $SCRIPT_DIR/piapi-mcp-server/dist/index.js"
echo ""
echo "You can now build the Docker image:"
echo "  docker build -f backend/Dockerfile ."
