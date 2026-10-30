# Publishing this repository

The working tree is prepared for a GitHub review; no staging, commit, push, or
remote repository settings were changed during this preparation.

## Included

Application source, migrations, Docker configurations, CI, reproduction steps,
architecture/behavior docs, synthetic screenshots, and sanitized benchmark evidence.
The benchmark archive contains only synthetic timing CSVs, run summaries, and
non-secret environment/source fingerprints.

## Excluded

Local `.env` configuration, private keys/certificates, SSH keys, `.backups/`
(including the recovery key and personal encrypted dumps), local benchmark output,
session manifests, dependency directories, build output, and logs. `.env.example`
is intentionally included with clearly identified local-only credentials.

The README describes the actual AWS deployment, but the public hostname and IP
are omitted from repository text. This reduces advertising; it is **not** access
control. The existing deployment remains reachable and registration remains open.
Invite-only registration, account quotas, and general API rate limiting have not
been added by this repository-preparation task. Do not describe it as invite-only.
Once those controls exist, add a live link and label it according to the real
access model, for example "Live Demo — account access by request".

## Your Git steps

From the repository root:

```sh
python3 scripts/check_repository.py
git status --short
git diff
```

Review the file list and changes, then stage the files you intend to publish.
`git add .` includes all unignored project changes, so use it only after reviewing
the list. Inspect new files too: `git diff` by itself does not show untracked files.
After staging:

```sh
git diff --cached --stat
git diff --cached
python3 scripts/check_repository.py
```

Check especially `.env.example`, deployment examples, screenshots, archives,
and configuration for sensitive values before committing and pushing:

```sh
git commit -m "Add analytics, extraction, matching, deployment and benchmarks"
git push origin main
```

The check script is read-only and also runs in CI. It detects common private-file
paths and private-key/API-token patterns in tracked/unignored candidates and
published benchmark archive contents. It does not verify absence of arbitrary
passwords or personal information, and it does not continuously scan Git history.
Existing history was separately scanned during this preparation with no findings
for those patterns. If an actual secret is committed, rotate it and review history
remediation before making the repository public; adding an ignore rule is insufficient.

No license has been selected automatically. Decide on a license separately if
you want to grant others permission to reuse or redistribute the project.
