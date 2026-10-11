#!/bin/sh
# Restore into a separately supplied, disposable database; never target production.
set -eu
: "${BACKUP_DATABASE_URL:?Set source PostgreSQL URI}"
: "${RESTORE_DATABASE_URL:?Set isolated restore PostgreSQL URI}"
: "${BACKUP_FILE:?Set protected backup destination}"
if [ "$BACKUP_DATABASE_URL" = "$RESTORE_DATABASE_URL" ]; then
  echo 'Restore target must differ from backup source' >&2
  exit 2
fi
umask 077
pg_dump "$BACKUP_DATABASE_URL" --format=custom --no-owner --file="$BACKUP_FILE"
pg_restore --dbname="$RESTORE_DATABASE_URL" --no-owner --exit-on-error "$BACKUP_FILE"
psql "$RESTORE_DATABASE_URL" -v ON_ERROR_STOP=1 -c 'SELECT PostGIS_Version(); SELECT count(*) FROM cities WHERE NOT ST_IsValid(boundary); SELECT count(*) FROM simulation_results;'
