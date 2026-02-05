#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="${1:-latest}"

echo "Using image tag: ${IMAGE_TAG}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH."
  exit 1
fi

if [ ! -f "docker-compose.yml" ] && [ ! -f "docker-compose.yaml" ] && [ ! -f "compose.yaml" ]; then
  echo "docker compose file not found in current directory."
  exit 1
fi

export IMAGE_TAG

echo "Pulling images with docker compose..."
docker compose pull

echo "Starting services with docker compose..."
docker compose up -d

echo "Deploy finished."
