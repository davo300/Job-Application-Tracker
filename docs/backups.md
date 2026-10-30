# Database backups for the private Lightsail deployment

Configured and restore-tested on October 29, 2026. No additional AWS services
were provisioned. Backup storage uses existing instance disk space and the Mac;
normal instance storage limits and network transfer allowances still apply.

## Schedule and retention

- Server: `job-tracker-backup.timer`, daily at **03:00 America/Detroit**, including
  daylight saving changes. Persistent scheduling catches a missed run after boot.
- Server retention: the **14 newest complete encrypted backup/checksum pairs**.
- Mac: `com.jobtracker.backup-sync` runs hourly while the Mac is awake and at
  agent load. It downloads all available complete files, verifies SHA-256 before
  publishing, and retains the **30 newest local copies**.
- Live database and backups are separate. Same-instance copies alone do not
  survive loss/deletion of the server; the downloaded Mac copies are the off-instance
  protection. If your Mac is off, asleep, disconnected, or its SSH key/IP changes,
  server backups continue but local copies cannot refresh until a successful sync.

The server captures a PostgreSQL custom-format consistent snapshot with schema
and data. It includes application records, description/analysis versions, profile
and match history, users/password hashes, and sessions. It excludes cluster roles,
Docker configuration, `.env`, and SSH keys. Recovery can use a newly generated
service password; application account password hashes are retained in the dump.

## Encryption and private files

OpenSSL CMS encrypts the compressed dump using AES-256-GCM and an RSA-OAEP
recipient key. Only the public certificate is on the server. Encryption uses
random per-backup keys; the private recovery key stays on the Mac. This follows
the [OpenSSL CMS encryption interface](https://docs.openssl.org/3.0/man1/openssl-cms/).

On the Mac, private files are beneath the repository's ignored `.backups/` directory:

- `recovery/private-key.pem`: recovery secret, mode 0600. **Keep a second secure
  copy in a password manager or encrypted offline storage. Losing this key makes
  encrypted backups unrecoverable.** It is not password-encrypted on this Mac;
  protect the Mac account/disk and preserve directory permissions.
- `recovery/recipient.pem`: public certificate; keep with the private key.
- `aws/`: encrypted dumps, checksums, and last-success marker.
- `pull.log` and `pull-error.log`: scheduled synchronization output.

Server files are under `/home/ubuntu/job-tracker-backups`, permission 0700.
Database data flows directly from pg_dump into encryption; no plaintext dump is
stored on the server. Atomic publication and checksums prevent incomplete files
being treated as successful backups. Retention only runs after successful writes.
Do not put recovery keys, plaintext dumps, or encrypted personal backups in Git.

## Status and manual operation

In the AWS browser SSH terminal:

```sh
systemctl list-timers job-tracker-backup.timer
systemctl show job-tracker-backup.service -p Result -p ExecMainStatus
sudo journalctl -u job-tracker-backup.service -n 20 --no-pager
sudo systemctl start job-tracker-backup.service
```

The oneshot service normally returns to `inactive (dead)` after a successful run;
`Result=success` and `ExecMainStatus=0` confirm it worked. A running timer is separate.

On your Mac, from the repository root (replace key path/IP if changed):

```sh
backend/.venv/bin/python scripts/backups/pull.py \
  --host ubuntu@SERVER_IP \
  --identity /path/to/LightsailDefaultKey-ca-central-1.pem \
  --directory .backups/aws
```

LaunchAgent file: `~/Library/LaunchAgents/com.jobtracker.backup-sync.plist`.
It depends on this repository, its backend Python environment, and the SSH key
remaining at the configured paths. Failures are logged; **email/push failure alerts
are not configured**. Check recent success regularly and after changing these paths.

## Verified recovery procedure

Decrypt a chosen downloaded backup to a protected scratch file:

```sh
umask 077
openssl cms -decrypt -binary -inform DER \
  -in .backups/aws/CHOSEN_BACKUP.dump.cms \
  -recip .backups/recovery/recipient.pem \
  -inkey .backups/recovery/private-key.pem \
  -out .backups/restore-check.dump
```

Abort on decryption failure; do not restore partial output. Run the rehearsal:

```sh
backend/.venv/bin/python scripts/backups/verify_restore.py \
  --host ubuntu@SERVER_IP \
  --identity /path/to/LightsailDefaultKey-ca-central-1.pem \
  --dump .backups/restore-check.dump
```

This creates a uniquely named empty verification database, restores with
`--exit-on-error`, compares row counts and sorted row digests across 10 persistent
tables, and drops only its own temporary database. Sessions are restored but excluded
from equivalence comparisons because they change during normal login/logout.
Concurrent app edits after the backup can cause expected differences; investigate
rather than assuming corruption. The live database is never overwritten.
Remove the local plaintext scratch dump after checking; normal deletion is not
secure erasure on SSDs. Prefer an encrypted local disk.

On October 29, encryption, download checksum, decryption, full restore, and the
10-table equivalence check all passed. The plaintext verification file and temporary
verification database were removed. The first hourly sync also passed.

For a real disaster, restore into a fresh database/instance, recreate roles and
secrets, verify readiness and authenticated reads, then deliberately switch the
application over. Do not use the rehearsal script to replace live data. Keep the
old database until recovery has been confirmed.

## Stopping schedules

On the server: `sudo systemctl disable --now job-tracker-backup.timer`.
On the Mac: `launchctl bootout gui/$(id -u)/com.jobtracker.backup-sync`.
These stop scheduling, not AWS billing. Do not delete the recovery key or wanted
backup copies when deleting the Lightsail instance.
