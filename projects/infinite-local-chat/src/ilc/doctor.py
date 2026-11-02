"""``ilc doctor``: check that this machine can run the assistant.

Each check is a pure function of a :class:`SystemInfo` snapshot, so the logic is tested without
depending on the machine the tests run on.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

GIB = 1024**3
MIN_RAM_GIB = 12  # ~7-8 GB for model + KV + embedder (design §3), plus room for macOS.
MIN_FREE_DISK_GIB = 10  # two GGUFs (~6 GB) plus the memory database and headroom.


class Status(Enum):
    """Outcome of one check."""

    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class Check:
    """Result of one doctor check."""

    name: str
    status: Status
    detail: str


@dataclass(frozen=True)
class SystemInfo:
    """Snapshot of the facts the checks need."""

    system: str  # platform.system(), e.g. "Darwin"
    machine: str  # platform.machine(), e.g. "arm64"
    python: tuple[int, int]
    ram_bytes: int | None
    free_disk_bytes: int | None
    llama_server_path: str | None


def total_ram_bytes() -> int | None:
    """Return physical RAM in bytes, or ``None`` if it cannot be determined."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        pass
    try:  # macOS fallback
        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5, check=True
        )
        return int(out.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def free_disk_bytes(path: Path) -> int | None:
    """Return free bytes on the filesystem holding ``path`` (or its nearest existing parent)."""
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return None


def gather(data_dir: Path) -> SystemInfo:
    """Collect a :class:`SystemInfo` snapshot of the current machine."""
    return SystemInfo(
        system=platform.system(),
        machine=platform.machine(),
        python=(sys.version_info.major, sys.version_info.minor),
        ram_bytes=total_ram_bytes(),
        free_disk_bytes=free_disk_bytes(data_dir),
        llama_server_path=shutil.which("llama-server"),
    )


def run_checks(info: SystemInfo) -> list[Check]:
    """Evaluate every check against ``info``.

    macOS/Apple Silicon is the supported target, but other platforms only warn so the package
    stays testable on Linux CI.
    """
    checks: list[Check] = []

    on_mac = info.system == "Darwin"
    checks.append(
        Check("platform", Status.OK if on_mac else Status.WARN, f"{info.system} (target: macOS)")
    )
    apple_silicon = on_mac and info.machine == "arm64"
    checks.append(
        Check(
            "apple silicon",
            Status.OK if apple_silicon else Status.WARN,
            info.machine + ("" if apple_silicon else " (Metal acceleration needs Apple Silicon)"),
        )
    )

    py_ok = info.python >= (3, 11)
    checks.append(
        Check(
            "python",
            Status.OK if py_ok else Status.FAIL,
            "{}.{} (need 3.11+)".format(*info.python),
        )
    )

    if info.ram_bytes is None:
        checks.append(Check("memory", Status.WARN, "could not determine total RAM"))
    else:
        gib = info.ram_bytes / GIB
        status = Status.OK if gib >= MIN_RAM_GIB else Status.WARN
        checks.append(Check("memory", status, f"{gib:.1f} GiB (recommended >= {MIN_RAM_GIB})"))

    if info.free_disk_bytes is None:
        checks.append(Check("disk", Status.WARN, "could not determine free disk space"))
    else:
        gib = info.free_disk_bytes / GIB
        status = Status.OK if gib >= MIN_FREE_DISK_GIB else Status.FAIL
        checks.append(Check("disk", status, f"{gib:.1f} GiB free (need >= {MIN_FREE_DISK_GIB})"))

    checks.append(
        Check(
            "llama-server",
            Status.OK if info.llama_server_path else Status.FAIL,
            info.llama_server_path or "not on PATH (install with: brew install llama.cpp)",
        )
    )
    return checks


def format_report(checks: list[Check]) -> str:
    """Render checks as aligned plain-text lines."""
    width = max(len(c.name) for c in checks)
    return "\n".join(f"[{c.status.value:>4}] {c.name:<{width}}  {c.detail}" for c in checks)
