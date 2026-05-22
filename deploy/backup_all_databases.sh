#!/bin/bash
# Nightly PostgreSQL backup for all local databases.
# Creates one directory per run:
#   globals.sql.gz       roles/tablespaces/cluster-wide grants
#   <database>.dump      custom-format dump for each connectable non-template DB
#
# Usage:
#   bash deploy/backup_all_databases.sh
# Optional env:
#   BACKUP_ROOT=/var/backups/eye_w/all_databases
#   RETENTION_DAYS=30

set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/eye_w/all_databases}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TARGET_DIR="$BACKUP_ROOT/$TIMESTAMP"
LOCK_FILE="/var/lock/eye_w_backup_all_databases.lock"

if ! command -v runuser >/dev/null 2>&1; then
  echo "runuser not found"
  exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1 || ! command -v pg_dumpall >/dev/null 2>&1; then
  echo "pg_dump/pg_dumpall not found"
  exit 1
fi

mkdir -p "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "backup already running"
  exit 0
fi

mkdir -p "$TARGET_DIR"
chmod 700 "$TARGET_DIR"

echo "backup started: $TARGET_DIR"

runuser -u postgres -- pg_dumpall --globals-only | gzip -9 > "$TARGET_DIR/globals.sql.gz"

mapfile -t DATABASES < <(
  runuser -u postgres -- psql -Atc "select datname from pg_database where datallowconn and not datistemplate order by datname"
)

{
  echo "timestamp=$TIMESTAMP"
  echo "retention_days=$RETENTION_DAYS"
  echo "databases=${DATABASES[*]}"
} > "$TARGET_DIR/manifest.txt"

for DB_NAME in "${DATABASES[@]}"; do
  SAFE_NAME="$(printf '%s' "$DB_NAME" | tr -c 'A-Za-z0-9_.-' '_')"
  runuser -u postgres -- pg_dump --format=custom "$DB_NAME" > "$TARGET_DIR/$SAFE_NAME.dump"
done

chmod -R go-rwx "$TARGET_DIR"

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +"$RETENTION_DAYS" -print -exec rm -rf {} +

echo "backup finished: $TARGET_DIR"
