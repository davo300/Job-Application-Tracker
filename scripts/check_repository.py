"""Read-only pre-publish checks; never stages files or prints matched secrets."""

import fnmatch
import re
import subprocess
import sys
import tarfile
from pathlib import Path

PRIVATE_NAMES = [
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "service-account*.json",
    "*.dump",
    "*.dump.*",
    "*.pgdump",
    "*.sql.gz",
]
TOKEN_PATTERNS = {
    "private key block": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "AWS access key identifier": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub token": re.compile(
        rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"
    ),
    "OpenAI project key": re.compile(rb"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
}
MAX_SCAN_BYTES = 10 * 1024 * 1024


def git_paths(*args):
    output = subprocess.check_output(["git", "ls-files", "-z", *args])
    return [name.decode() for name in output.split(b"\0") if name]


def private_path(name):
    path = Path(name)
    if any(part in {".backups", ".aws", ".ssh"} for part in path.parts):
        return True
    if path.name == ".env" or path.name.startswith(".env."):
        return not fnmatch.fnmatch(path.name, ".env*.example")
    if path.name.endswith(".env"):
        return True
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in PRIVATE_NAMES)


def scan_bytes(name, content, findings):
    for category, pattern in TOKEN_PATTERNS.items():
        match = pattern.search(content)
        if match:
            line = content[: match.start()].count(b"\n") + 1
            findings.append(f"{name}:{line}: possible {category} (value redacted)")


def main():
    root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    )
    if Path.cwd() != root:
        print("Run from the repository root.", file=sys.stderr)
        return 2
    candidates = sorted(set(git_paths("--cached", "--others", "--exclude-standard")))
    findings = []
    for name in git_paths("--cached", "--ignored", "--exclude-standard"):
        findings.append(
            f"{name}: tracked file now matches an ignore rule; review before publishing"
        )
    for name in candidates:
        path = root / name
        if private_path(name):
            findings.append(f"{name}: private file must not be committed")
            continue
        if path.is_symlink():
            findings.append(f"{name}: symlink requires manual review")
            continue
        if not path.is_file():
            continue
        if name.endswith(".tar.gz"):
            # Published benchmark archives must contain synthetic CSV/JSON only.
            try:
                with tarfile.open(path, "r:gz") as archive:
                    for member in archive:
                        inner = Path(member.name)
                        if (
                            not member.isfile()
                            or len(inner.parts) != 1
                            or inner.suffix not in {".csv", ".json"}
                            or private_path(member.name)
                        ):
                            findings.append(
                                f"{name}: unexpected archive member {member.name}"
                            )
                            continue
                        if member.size > MAX_SCAN_BYTES:
                            findings.append(
                                f"{name}:{member.name}: too large for automated scan"
                            )
                            continue
                        source = archive.extractfile(member)
                        if source:
                            scan_bytes(f"{name}:{member.name}", source.read(), findings)
            except tarfile.TarError:
                findings.append(f"{name}: archive cannot be inspected")
        elif path.stat().st_size > MAX_SCAN_BYTES:
            findings.append(f"{name}: too large for automated scan")
        else:
            scan_bytes(name, path.read_bytes(), findings)
    if findings:
        print("Review required (no secret values displayed):")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(
        f"Checked {len(candidates)} tracked/unignored files and archive contents: no private-path or common token-pattern findings."
    )
    print(
        "This is a limited pattern scan, not a guarantee. Review staged diffs and screenshots manually."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
