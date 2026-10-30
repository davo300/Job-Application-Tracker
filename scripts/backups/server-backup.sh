#!/bin/bash
# Installed as a root-owned script; systemd runs this as the ubuntu account.
set -euo pipefail
umask 077
APP_DIR=/home/ubuntu/job-tracker
BACKUP_DIR=/home/ubuntu/job-tracker-backups
RECIPIENT=/etc/job-tracker-backup-recipient.pem
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
exec 9>"$BACKUP_DIR/.backup.lock"
flock -n 9 || exit 0
partial=$(mktemp "$BACKUP_DIR/.partial-XXXXXX")
trap 'rm -f "$partial"' EXIT
name="tracker-$(date -u +%Y%m%dT%H%M%SZ).dump.cms"
# Compressed consistent snapshot, including schema/data, without cluster roles.
sudo -n docker compose --project-directory "$APP_DIR" -f "$APP_DIR/compose.tunnel.yml" \
  exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl' \
  | openssl cms -encrypt -binary -aes-256-gcm -outform DER -recip "$RECIPIENT" \
      -keyopt rsa_padding_mode:oaep -out "$partial"
test -s "$partial"
openssl cms -cmsout -inform DER -in "$partial" -noout
mv -n "$partial" "$BACKUP_DIR/$name"
(cd "$BACKUP_DIR" && sha256sum "$name" > "$name.sha256")
# Prune only complete backup pairs after successful backup creation.
python3 - "$BACKUP_DIR" <<'PY'
from pathlib import Path
import re
import sys
root=Path(sys.argv[1])
files=sorted(p for p in root.iterdir() if re.fullmatch(r'tracker-\d{8}T\d{6}Z\.dump\.cms', p.name) and not p.is_symlink() and p.with_name(p.name+'.sha256').is_file())
for p in files[:-14]:
    p.unlink()
    p.with_name(p.name+'.sha256').unlink()
PY
touch "$BACKUP_DIR/last-success"
printf 'Encrypted database backup completed: %s\n' "$name"
