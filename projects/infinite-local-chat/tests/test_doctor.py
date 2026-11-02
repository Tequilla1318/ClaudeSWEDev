from dataclasses import replace

import pytest

from ilc.doctor import GIB, Status, SystemInfo, format_report, free_disk_bytes, gather, run_checks

OWNER_MAC = SystemInfo(
    system="Darwin",
    machine="arm64",
    python=(3, 11),
    ram_bytes=16 * GIB,
    free_disk_bytes=100 * GIB,
    llama_server_path="/opt/homebrew/bin/llama-server",
)


def by_name(info: SystemInfo) -> dict[str, Status]:
    return {c.name: c.status for c in run_checks(info)}


def test_owner_mac_passes_everything():
    assert set(by_name(OWNER_MAC).values()) == {Status.OK}


@pytest.mark.parametrize(
    "change, name, expected",
    [
        ({"system": "Linux", "machine": "x86_64"}, "platform", Status.WARN),
        ({"system": "Linux", "machine": "x86_64"}, "apple silicon", Status.WARN),
        ({"machine": "x86_64"}, "apple silicon", Status.WARN),  # Intel Mac
        ({"python": (3, 10)}, "python", Status.FAIL),
        ({"ram_bytes": 8 * GIB}, "memory", Status.WARN),
        ({"ram_bytes": None}, "memory", Status.WARN),
        ({"free_disk_bytes": 5 * GIB}, "disk", Status.FAIL),
        ({"free_disk_bytes": None}, "disk", Status.WARN),
        ({"llama_server_path": None}, "llama-server", Status.FAIL),
    ],
)
def test_individual_checks(change, name, expected):
    assert by_name(replace(OWNER_MAC, **change))[name] is expected


def test_missing_llama_server_tells_how_to_install():
    checks = run_checks(replace(OWNER_MAC, llama_server_path=None))
    detail = next(c.detail for c in checks if c.name == "llama-server")
    assert "brew install llama.cpp" in detail


def test_report_has_one_line_per_check():
    checks = run_checks(OWNER_MAC)
    lines = format_report(checks).splitlines()
    assert len(lines) == len(checks)
    assert lines[0].startswith("[  ok] platform")


def test_free_disk_walks_up_to_existing_parent(tmp_path):
    assert free_disk_bytes(tmp_path / "does" / "not" / "exist") == free_disk_bytes(tmp_path)


def test_gather_on_this_machine_returns_plausible_values(tmp_path):
    info = gather(tmp_path)
    assert info.python >= (3, 11)
    assert info.ram_bytes is None or info.ram_bytes > GIB
    assert info.free_disk_bytes is not None
