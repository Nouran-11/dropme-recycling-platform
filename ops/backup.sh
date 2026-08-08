#!/usr/bin/env bash
# Dump the database to a compressed, verified custom-format archive and prune
# old dumps. Connection comes from standard libpq env vars (PGHOST, PGUSER,
# PGPASSWORD, PGDATABASE). Exits non-zero on any failure so a caller/cron
# notices a broken backup instead of trusting an empty file.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
GIT_SHA="${GIT_SHA:-unknown}"
PGDATABASE="${PGDATABASE:-dropme}"

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
dumpfile="$BACKUP_DIR/dropme_${timestamp}_${GIT_SHA}.dump"

echo "[backup] dumping database '$PGDATABASE' -> $dumpfile"
pg_dump -Fc -f "$dumpfile" "$PGDATABASE"

# Verify the archive's table of contents is readable before we trust it.
echo "[backup] verifying archive is readable (pg_restore --list)"
pg_restore --list "$dumpfile" >/dev/null

echo "[backup] compressing"
gzip -f "$dumpfile"
gzfile="${dumpfile}.gz"

echo "[backup] verifying gzip integrity"
gzip -t "$gzfile"

echo "[backup] pruning dumps older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -name 'dropme_*.dump.gz' -type f -mtime +"$RETENTION_DAYS" -print -delete

echo "[backup] OK: $gzfile ($(du -h "$gzfile" | cut -f1))"
