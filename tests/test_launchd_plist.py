"""Sanity-check the launchd plist: well-formed XML, paths resolve."""
import plistlib
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
PLIST = HERE.parent / "launchd" / "com.jwalinshah.agy-quota-scraper.plist"


def test_plist_is_well_formed_xml():
    ET.parse(PLIST)


def test_plist_parses_with_plistlib():
    data = plistlib.loads(PLIST.read_bytes())
    assert data["Label"] == "com.jwalinshah.agy-quota-scraper"
    assert data["RunAtLoad"] is True
    assert data["StartInterval"] == 600
    # Background mode is the whole point
    argv = data["ProgramArguments"]
    assert "--background" in argv
    # The actual program + script must exist
    program = argv[0]
    script = argv[1]
    assert Path(program).exists(), f"interpreter missing: {program}"
    assert Path(script).exists(), f"script missing: {script}"


def test_plist_stdout_stderr_paths_are_under_quota_status_dir():
    data = plistlib.loads(PLIST.read_bytes())
    for key in ("StandardOutPath", "StandardErrorPath"):
        path = Path(data[key])
        assert path.parent.name == ".quota-status", f"{key} {path} not in ~/.quota-status/"


def test_plist_environment_includes_home_and_path():
    data = plistlib.loads(PLIST.read_bytes())
    env = data["EnvironmentVariables"]
    assert "PATH" in env
    assert "HOME" in env
