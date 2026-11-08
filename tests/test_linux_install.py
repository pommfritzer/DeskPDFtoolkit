import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux desktop integration")


@pytest.fixture
def distribution(tmp_path):
    root = Path(__file__).resolve().parents[1]
    folder = tmp_path / "download"
    assets = folder / "_internal" / "deskpdf" / "assets"
    assets.mkdir(parents=True)
    (assets / "icon.png").write_bytes(b"icon")
    (folder / "PDFtoolkit26").write_text("first version", encoding="utf-8")
    shutil.copy(root / "scripts" / "install-linux.sh", folder / "install.sh")
    shutil.copy(root / "scripts" / "uninstall-linux.sh", folder / "uninstall.sh")
    return folder


def test_install_upgrade_and_uninstall(distribution, tmp_path):
    data = tmp_path / 'home with space % $ " ` \\' / "data"
    env = {**os.environ, "HOME": str(tmp_path), "XDG_DATA_HOME": str(data)}
    install = ["sh", str(distribution / "install.sh")]
    subprocess.run(install, env=env, check=True, capture_output=True, text=True)
    target = data / "pdftoolkit26"
    desktop = data / "applications" / "org.pdftoolkit26.desktop"
    assert (target / "PDFtoolkit26").read_text(encoding="utf-8") == "first version"
    assert (target / ".pdftoolkit26-managed").is_file()
    entry = desktop.read_text(encoding="utf-8")
    assert 'Name=PDFtoolkit26' in entry and 'MimeType=application/pdf;' in entry
    assert 'Exec=/bin/sh -c ' in entry and ' %F' in entry
    if shutil.which("desktop-file-validate"):
        subprocess.run(["desktop-file-validate", str(desktop)], check=True, capture_output=True, text=True)
    (distribution / "PDFtoolkit26").write_text("second version", encoding="utf-8")
    subprocess.run(install, env=env, check=True, capture_output=True, text=True)
    assert (target / "PDFtoolkit26").read_text(encoding="utf-8") == "second version"
    assert not list(data.glob(".pdftoolkit26-old.*"))
    subprocess.run(["sh", str(target / "uninstall.sh")], env=env, check=True, capture_output=True, text=True)
    assert not target.exists() and not desktop.exists()


def test_installer_does_not_replace_unmanaged_files(distribution, tmp_path):
    data = tmp_path / "data"
    target = data / "pdftoolkit26"
    target.mkdir(parents=True)
    important = target / "keep.txt"
    important.write_text("keep", encoding="utf-8")
    env = {**os.environ, "HOME": str(tmp_path), "XDG_DATA_HOME": str(data)}
    result = subprocess.run(["sh", str(distribution / "install.sh")], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert important.read_text(encoding="utf-8") == "keep"


def test_installer_rejects_shortcut_symlink(distribution, tmp_path):
    data = tmp_path / "data"
    applications = data / "applications"
    applications.mkdir(parents=True)
    important = tmp_path / "keep.desktop"
    important.write_text("keep", encoding="utf-8")
    (applications / "org.pdftoolkit26.desktop").symlink_to(important)
    env = {**os.environ, "HOME": str(tmp_path), "XDG_DATA_HOME": str(data)}
    result = subprocess.run(["sh", str(distribution / "install.sh")], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert important.read_text(encoding="utf-8") == "keep"

@pytest.mark.parametrize("directory", ["plain path", "percent %", "dollar $", 'quote "', "tick `", "backslash \\"])
def test_desktop_entry_launches_pdf_paths(distribution, tmp_path, directory):
    import time
    gio = shutil.which("gio")
    if not gio:
        pytest.skip("gio is not installed")
    executable = distribution / "PDFtoolkit26"
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$PDFTOOLKIT26_TEST_ARGUMENTS"\n', encoding="utf-8")
    executable.chmod(0o755)
    data = tmp_path / directory / "data"
    arguments = tmp_path / "received.txt"
    document = tmp_path / "a file \u00dc.pdf"
    document.write_bytes(b"test")
    env = {**os.environ, "HOME": str(tmp_path), "XDG_DATA_HOME": str(data), "PDFTOOLKIT26_TEST_ARGUMENTS": str(arguments)}
    subprocess.run(["sh", str(distribution / "install.sh")], env=env, check=True, capture_output=True, text=True)
    desktop = data / "applications" / "org.pdftoolkit26.desktop"
    result = subprocess.run([gio, "launch", str(desktop), str(document)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, f"{result.stderr}\n{desktop.read_text(encoding='utf-8')}"
    deadline = time.monotonic() + 5
    while not arguments.exists() and time.monotonic() < deadline:
        time.sleep(.05)
    assert arguments.read_text(encoding="utf-8").splitlines() == [str(document)]
