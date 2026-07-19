#!/usr/bin/env bash
# MyOriShop — nightly pg_dump backup with 30-day retention (Plan 28-06, T-28-30).
#
# Invoked by myorishop-pgbackup.service on the schedule set in the timer.
set -euo pipefail

# Where dumps are written. Override via the environment if you keep them
# elsewhere. Keep this OFF the PostgreSQL data directory.
BACKUP_DIR="${BACKUP_DIR:-/var/backups/myorishop}"
# Retention window in days — matches the client's backup_keep: 30.
KEEP_DAYS="${KEEP_DAYS:-30}"

# Connection details come from the standard libpq environment variables
# (PGHOST, PGPORT, PGUSER, PGDATABASE and PGPASSWORD or a ~/.pgpass entry),
# supplied by the systemd unit's EnvironmentFile. NEVER hardcode credentials
# here and NEVER echo the connection string or password (CLAUDE.md safety):
# pg_dump reads them implicitly, so no secret ever lands on the command line
# or in journalctl.
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_DIR/myorishop-$STAMP.dump"

# Custom-format dump (-Fc): compressed and restorable with pg_restore. The
# database NAME is not a secret; the credentials stay in the environment.
pg_dump -Fc -f "$TARGET" "${PGDATABASE:-myorishop}"

# Retention: delete dumps older than KEEP_DAYS. A backup on the SAME disk is
# NOT a backup — copying these dumps OFF the box (object storage, another host)
# remains the operator's responsibility; this script does not do it for you.
find "$BACKUP_DIR" -name 'myorishop-*.dump' -type f -mtime "+$KEEP_DAYS" -delete
