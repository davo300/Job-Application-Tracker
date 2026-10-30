"""Capture selected non-secret benchmark environment and source fingerprints."""

import hashlib
import json
import platform
import subprocess
from pathlib import Path


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    root = Path(__file__).resolve().parent.parent
    sources = sorted(
        [
            *root.glob("backend/app/**/*.py"),
            *root.glob("benchmarks/*.py"),
            root / "benchmarks/compose.yml",
            root / "backend/Dockerfile",
            root / "backend/requirements-dev.lock",
        ]
    )
    data = {
        "host": {"os": platform.platform(), "machine": platform.machine()},
        "git_head": command("git", "rev-parse", "HEAD"),
        "working_tree_dirty": bool(command("git", "status", "--porcelain")),
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sources
        },
        "docker": json.loads(command("docker", "info", "--format", "{{json .}}")),
    }
    # Docker info has many unrelated machine fields; retain only capacity/version.
    data["docker"] = {
        key: data["docker"].get(key)
        for key in [
            "ServerVersion",
            "NCPU",
            "MemTotal",
            "Architecture",
            "OperatingSystem",
            "KernelVersion",
        ]
    }
    if platform.system() == "Darwin":
        for key in ["machdep.cpu.brand_string", "hw.ncpu", "hw.memsize"]:
            data["host"][key] = command("sysctl", "-n", key)
    data["images"] = {
        image: command("docker", "image", "inspect", image, "--format", "{{.Id}}")
        for image in ["tracker-benchmark-backend", "postgres:17-alpine"]
    }

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
