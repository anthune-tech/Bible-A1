#!/bin/bash

kill $(lsof -t -i:8000) 2>/dev/null

# Wait for ollama (systemd service) to be ready
for i in $(seq 1 30); do
  if curl -s http://localhost:11434 > /dev/null 2>&1; then break; fi
  sleep 1
done

# If dev mode, start Vite dev server instead
if [ "$1" = "dev" ]; then
  echo "Starting Vite dev server (API proxied to Python on :8000)..."
  python3 server.py > /tmp/server.log 2>&1 &
  echo "Python API server starting on http://localhost:8000"
  # Use npx or find node in common locations
  for nodebin in /tmp/node-v22.12.0-linux-x64/bin/npx /usr/local/bin/npx npx; do
    if command -v $nodebin &>/dev/null; then
      $nodebin vite --host &
      break
    fi
  done
  echo "  Vite:   http://localhost:5173"
  echo "  API:    http://localhost:8000"
  exit 0
fi

python3 server.py > /tmp/server.log 2>&1 &

echo "Services started"
echo "  Ollama: http://localhost:11434"
echo "  Bible:  http://localhost:8000"
echo ""
echo "For development with hot reload: ./start.sh dev"
