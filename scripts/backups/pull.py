"""Copy only complete encrypted backups over SSH; never needs the recovery key."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

INDEX = r"""
from pathlib import Path
import json, re
root=Path.home()/'job-tracker-backups'
rows=[]
for p in sorted(root.glob('tracker-*.dump.cms')):
    checksum=p.with_name(p.name+'.sha256')
    if not re.fullmatch(r'tracker-\d{8}T\d{6}Z\.dump\.cms',p.name) or p.is_symlink() or not checksum.is_file():
        continue
    digest=checksum.read_text().split()[0]
    if re.fullmatch(r'[a-f0-9]{64}',digest):
        rows.append({'name':p.name,'sha256':digest})
print(json.dumps(rows))
"""


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.@:-]*", args.host):
        parser.error("Invalid SSH host")
    args.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(args.directory, 0o700)
    options = [
        "-i",
        str(args.identity),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=3",
    ]
    result = subprocess.run(
        ["/usr/bin/ssh", *options, args.host, "python3 -"],
        input=INDEX,
        text=True,
        check=True,
        capture_output=True,
        timeout=60,
    )
    entries = json.loads(result.stdout)
    if not entries:
        raise RuntimeError("No complete backups available on server")
    copied = 0
    for entry in entries:
        name, sha = entry["name"], entry["sha256"]
        if not re.fullmatch(
            r"tracker-\d{8}T\d{6}Z\.dump\.cms", name
        ) or not re.fullmatch(r"[a-f0-9]{64}", sha):
            raise ValueError("Invalid backup index")
        destination = args.directory / name
        if (
            destination.is_file()
            and not destination.is_symlink()
            and digest(destination) == sha
        ):
            continue
        fd, tmp = tempfile.mkstemp(prefix=".partial-", dir=args.directory)
        os.close(fd)
        temporary = Path(tmp)
        try:
            subprocess.run(
                [
                    "/usr/bin/scp",
                    *options,
                    f"{args.host}:job-tracker-backups/{name}",
                    str(temporary),
                ],
                check=True,
                timeout=300,
            )
            if digest(temporary) != sha:
                raise ValueError("Downloaded backup checksum mismatch")
            os.chmod(temporary, 0o600)
            temporary.replace(destination)
            destination.with_name(name + ".sha256").write_text(f"{sha}  {name}\n")
            os.chmod(destination.with_name(name + ".sha256"), 0o600)
            copied += 1
        finally:
            temporary.unlink(missing_ok=True)
    # Prune local copies only after a verified latest backup is present.
    files = sorted(
        p
        for p in args.directory.iterdir()
        if re.fullmatch(r"tracker-\d{8}T\d{6}Z\.dump\.cms", p.name)
        and not p.is_symlink()
    )
    for old in files[:-30]:
        old.unlink()
        old.with_name(old.name + ".sha256").unlink(missing_ok=True)
    (args.directory / "last-success").write_text(entries[-1]["name"] + "\n")
    print(f"Backup sync succeeded: {copied} copied; latest {entries[-1]['name']}")


if __name__ == "__main__":
    main()
