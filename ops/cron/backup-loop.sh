#!/usr/bin/env bash
# Minimal in-container scheduler for the local stack. A failed backup logs and
# the loop continues so one bad run does not stop future backups.
#
# Production would not use this: prefer a managed snapshot schedule (e.g. RDS
# automated backups) plus dumps to versioned object storage with lifecycle
# rules, and WAL archiving for point-in-time recovery.
set -uo pipefail

INTERVAL="${BACKUP_INTERVAL:-3600}"
echo "[backup-loop] running backup every ${INTERVAL}s"
while true; do
  bash /ops/backup.sh || echo "[backup-loop] backup FAILED (will retry next interval)"
  sleep "$INTERVAL"
done
