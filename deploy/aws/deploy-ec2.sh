#!/usr/bin/env bash
# ==============================================================================
# Turnkey Setup Script for AWS Free Tier EC2 (Amazon Linux 2023 or Ubuntu)
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo " Starting Gemini Cost Arbiter MCP Setup on AWS EC2..."
echo "=========================================================="

# 1. Detect OS and install Docker & Docker Compose
if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "$ID" in
        amzn)
            echo "[+] Detected Amazon Linux. Installing Docker..."
            sudo dnf update -y
            sudo dnf install -y docker git
            sudo systemctl enable --now docker
            sudo usermod -aG docker "$USER"
            # Install Docker Compose Plugin
            DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
            mkdir -p "$DOCKER_CONFIG/cli-plugins"
            curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m) -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
            chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
            ;;
        ubuntu|debian)
            echo "[+] Detected Ubuntu/Debian. Installing Docker..."
            sudo apt-get update -y
            sudo apt-get install -y ca-certificates curl gnupg git
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo chmod a+r /etc/apt/keyrings/docker.gpg
            echo \
              "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
              "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
              sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt-get update -y
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            sudo usermod -aG docker "$USER"
            ;;
        *)
            echo "[-] Unsupported OS ID: $ID. Please install Docker manually."
            exit 1
            ;;
    esac
fi

# 2. Setup persistent data directory
mkdir -p data
sudo chmod 777 data

# 3. Initialize .env file if missing
if [ ! -f .env ]; then
    echo "[+] Creating .env configuration from template..."
    cp .env.example .env
    echo "=========================================================="
    echo " IMPORTANT: Edit .env and supply your GEMINI_API_KEY:"
    echo " nano .env"
    echo "=========================================================="
fi

echo "[+] Setup completed successfully!"
echo "To start the container, run:"
echo "  docker compose -f deploy/aws/docker-compose.prod.yml up -d"
