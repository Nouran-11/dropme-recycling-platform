#!/usr/bin/env bash
# Restore a dump into a scratch database by default, so verifying a backup is
# non-destructive. `--target production` restores into the live database and
# requires typing its name to confirm. Connection comes from libpq env vars.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
SCRATCH_DB="${SCRATCH_DB:-dropme_restore_test}"
PROD_DB="${PGDATABASE:-dropme}"

target="scratch"
dump=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) target="${2:-}"; shift 2 ;;
    *) dump="$1"; shift ;;
  esac
done

# Default to the newest dump if a file was not given.
if [[ -z "$dump" ]]; then
  dump="$(ls -1t "$BACKUP_DIR"/dropme_*.dump.gz 2>/dev/null | head -1 || true)"
fi
if [[ -z "$dump" || ! -f "$dump" ]]; then
  echo "[restore] no dump file found (looked in $BACKUP_DIR)" >&2
  exit 1
fi

if [[ "$target" == "production" ]]; then
  db="$PROD_DB"
  echo "[restore] !!! about to OVERWRITE production database '$db' from $dump"
  read -r -p "Type the database name '$db' to confirm: " reply
  if [[ "$reply" != "$db" ]]; then
    echo "[restore] confirmation did not match; aborting" >&2
    exit 1
  fi
  echo "[restore] restoring into production '$db'"
  gunzip -c "$dump" | pg_restore --clean --if-exists --no-owner --dbname="$db"
else
  db="$SCRATCH_DB"
  echo "[restore] recreating scratch database '$db'"
  psql -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$db\";"
  psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$db\";"
  echo "[restore] restoring $dump into '$db'"
  gunzip -c "$dump" | pg_restore --no-owner --dbname="$db"
fi

echo "[restore] OK: restored '$db' from $dump"
