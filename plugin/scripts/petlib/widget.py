"""Desktop widget (app/): find it, launch it on session start, install and update it from GitHub Releases."""
from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

APP_NAME = "Token Pet.app"
RELEASE_URL = "https://github.com/ara-zo/token-pet/releases/latest/download/Token-Pet-macos.zip"
LATEST_URL = "https://github.com/ara-zo/token-pet/releases/latest"     # redirects to .../tag/vX.Y.Z


def _candidates() -> list:
    return [Path("/Applications") / APP_NAME, Path.home() / "Applications" / APP_NAME]


def find_app() -> Optional[Path]:
    for p in _candidates():
        if p.is_dir():
            return p
    return None


def launch(app: Optional[Path] = None) -> bool:
    """Open the widget in the background. `open` on a running app is a no-op, so no need to check."""
    if sys.platform != "darwin":
        return False
    app = app or find_app()
    if app is None:
        return False
    subprocess.Popen(["open", "-g", str(app)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return True


def _version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def installed_version(app: Path) -> Optional[str]:
    try:
        with open(app / "Contents" / "Info.plist", "rb") as f:
            return plistlib.load(f).get("CFBundleShortVersionString")
    except (OSError, ValueError):
        return None


def latest_version() -> Optional[str]:
    """Tag of the latest release, read from the redirect so no API token or rate limit is involved."""
    r = subprocess.run(["curl", "-fsSI", "--max-time", "10", LATEST_URL], capture_output=True, text=True)
    m = re.search(r"^location:.*/tag/v?([\w.]+)\s*$", r.stdout, re.I | re.M)
    return m.group(1) if m else None


def _running() -> bool:
    return subprocess.run(["pgrep", "-f", APP_NAME + "/Contents/MacOS/"], capture_output=True).returncode == 0


def _wait(running: bool, tries: int = 50) -> bool:
    for _ in range(tries):
        if _running() == running:
            return True
        time.sleep(0.1)
    return False


def _quit_running() -> None:
    """Quit the widget and wait for it to exit; `open` on a still-quitting app does nothing.
    An app that ignores the quit request within 5 s is stopped."""
    subprocess.run(["osascript", "-e", 'quit app "Token Pet"'], capture_output=True)
    if not _wait(False):
        subprocess.run(["pkill", "-f", APP_NAME + "/Contents/MacOS/"], capture_output=True)
        _wait(False)


def _relaunch(app: Path) -> None:
    """Start the freshly installed copy and make sure it is up: one `open` right after replacing
    the app did not always start it, which left the widget gone after an update."""
    for _ in range(3):
        subprocess.run(["open", "-g", str(app)], capture_output=True)
        if _wait(True, 30):
            return


def install(dest_dir: Optional[Path] = None) -> Path:
    """Download the latest release and launch it. Replaces an installed copy in place (so login items keep
    pointing at it), else goes to ~/Applications. Raises RuntimeError with a user-facing message."""
    if sys.platform != "darwin":
        raise RuntimeError("위젯은 macOS에서만 돼요")
    if dest_dir is None:
        current = find_app()
        dest_dir = current.parent if current else Path.home() / "Applications"
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "widget.zip")
        r = subprocess.run(["curl", "-fsSL", "-o", zip_path, RELEASE_URL], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"위젯을 받지 못했어요 ({RELEASE_URL})\n{r.stderr.strip()}")
        r = subprocess.run(["ditto", "-x", "-k", zip_path, tmp], capture_output=True, text=True)
        src = Path(tmp) / APP_NAME
        if r.returncode != 0 or not src.is_dir():
            raise RuntimeError(f"받은 파일을 풀지 못했어요\n{r.stderr.strip()}")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / APP_NAME
        if dest.exists():
            _quit_running()
            shutil.rmtree(dest)
        shutil.move(str(src), str(dest))
    # unsigned build: drop the quarantine flag so Gatekeeper doesn't block the first open
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(dest)], capture_output=True)
    _relaunch(dest)
    return dest


def update() -> Optional[tuple]:
    """Install the latest release over an older installed widget. Returns (old, new) when it updated."""
    app = find_app()
    if app is None:
        raise RuntimeError("위젯이 설치돼 있지 않아요. /pet widget install 로 설치해 주세요")
    have, latest = installed_version(app), latest_version()
    if latest is None:
        raise RuntimeError("최신 버전을 확인하지 못했어요. 네트워크를 확인해 주세요")
    if have and _version_tuple(have) >= _version_tuple(latest):
        return None
    install(app.parent)
    return (have, latest)
