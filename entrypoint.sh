#!/bin/bash

# Exit on any error
set -e

echo "Starting Celery worker in background..."

# Celery worker
poetry run celery -A ui_dash_hitl:celery_app worker --loglevel=INFO --concurrency=2 &

# Run the main container command
exec "$@"
