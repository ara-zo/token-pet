"""Desktop widget (app/): find it, launch it on session start, install it from GitHub Releases."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

APP_NAME = "Token Pet.app"
RELEASE_URL = "https://github.com/ara-zo/token-pet/releases/latest/download/Token-Pet-macos.zip"


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


def install() -> Path:
    """Download the latest release into ~/Applications and launch it. Raises RuntimeError with a user-facing message."""
    if sys.platform != "darwin":
        raise RuntimeError("위젯은 macOS에서만 돼요")
    dest_dir = Path.home() / "Applications"
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
            shutil.rmtree(dest)
        shutil.move(str(src), str(dest))
    # unsigned build: drop the quarantine flag so Gatekeeper doesn't block the first open
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(dest)], capture_output=True)
    launch(dest)
    return dest
