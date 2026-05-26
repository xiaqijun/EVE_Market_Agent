#!/bin/bash
# First-time server setup for EVE Market Agent
# Run this ONCE on the target server after cloning the repository.
# Usage: bash scripts/setup-server.sh

set -e

echo "=== EVE Market Agent Server Setup ==="
echo ""

# 1. Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required. Install: https://docs.docker.com/engine/install/"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required."; exit 1; }
echo "✅ Docker and Docker Compose found"

# 2. Create secrets directory
mkdir -p secrets
echo ""

# 3. Generate secrets
if [ ! -f secrets/jwt_secret.txt ]; then
    openssl rand -hex 32 > secrets/jwt_secret.txt
    echo "✅ Generated JWT_SECRET"
else
    echo "⏭  JWT_SECRET already exists"
fi

if [ ! -f secrets/encryption_key.txt ]; then
    openssl rand -hex 32 > secrets/encryption_key.txt
    echo "✅ Generated ENCRYPTION_KEY"
else
    echo "⏭  ENCRYPTION_KEY already exists"
fi

# 4. Collect API keys
echo ""
echo "Enter your API keys (press Enter to skip):"

if [ ! -f secrets/anthropic_api_key.txt ]; then
    read -p "Anthropic API Key: " anthropic_key
    echo "$anthropic_key" > secrets/anthropic_api_key.txt
fi

if [ ! -f secrets/openai_api_key.txt ]; then
    read -p "OpenAI API Key: " openai_key
    echo "$openai_key" > secrets/openai_api_key.txt
fi

if [ ! -f secrets/deepseek_api_key.txt ]; then
    read -p "DeepSeek API Key: " deepseek_key
    echo "$deepseek_key" > secrets/deepseek_api_key.txt
fi

# 5. Generate Webhook Secret
if [ ! -f secrets/webhook_secret.txt ]; then
    openssl rand -hex 16 > secrets/webhook_secret.txt
    echo "✅ Generated WEBHOOK_SECRET"
fi

# 6. Create .env from example
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env from .env.example"
else
    echo "⏭  .env already exists"
fi

# 7. Set up GitHub webhook secret
WEBHOOK_SECRET=$(cat secrets/webhook_secret.txt)
echo ""
echo "=== GitHub Setup ==="
echo "Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):"
echo "  DEPLOY_WEBHOOK_URL:  https://your-server.com/webhook/deploy"
echo "  WEBHOOK_SECRET:      $WEBHOOK_SECRET"
echo ""

# 8. Pull images and start
echo "=== Starting services ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull 2>/dev/null || echo "(Images will be pulled on first deploy)"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo ""
echo "✅ Setup complete!"
echo "   Access: http://localhost"
echo "   Webhook receiver: http://localhost:9000/webhook/deploy"
echo ""
echo "To see logs: docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
