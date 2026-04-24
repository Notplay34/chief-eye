#!/bin/bash
# PostgreSQL backup for eye_w.
# Usage: bash deploy/backup_db.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/backend/.env"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/eye_w}"

if [ ! -f "$ENV_FILE" ]; then
  echo "backend/.env не найден"
  exit 1
fi

mkdir -p "$BACKUP_DIR"

DATABASE_URL="$(grep '^DATABASE_URL=' "$ENV_FILE" | cut -d= -f2-)"
if [ -z "$DATABASE_URL" ]; then
  echo "DATABASE_URL не задан"
  exit 1
fi

SYNC_URL="${DATABASE_URL#postgresql+asyncpg://}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TARGET="$BACKUP_DIR/eye_w_$TIMESTAMP.dump"

pg_dump --format=custom --file="$TARGET" "postgresql://$SYNC_URL"
echo "$TARGET"
