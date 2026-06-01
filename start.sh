#!/bin/bash

kill $(lsof -t -i:8000) 2>/dev/null

# Wait for ollama (systemd service) to be ready
for i in $(seq 1 30); do
  if curl -s http://localhost:11434 > /dev/null 2>&1; then break; fi
  sleep 1
done

python3 server.py > /tmp/server.log 2>&1 &

echo "Services started"
echo "  Ollama: http://localhost:11434"
echo "  Bible:  http://localhost:8000"
