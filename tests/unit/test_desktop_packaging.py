"""Regression checks for desktop packaging inputs."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_desktop_package_keeps_build_configuration():
    package = json.loads((PROJECT_ROOT / "desktop" / "package.json").read_text(encoding="utf-8"))

    assert package["scripts"]["build:win"] == "electron-builder --win --x64"
    assert package["scripts"]["build:mac"] == "electron-builder --mac --arm64"
    assert package["devDependencies"]["electron"]
    assert package["devDependencies"]["electron-builder"]
    assert package["build"]["appId"] == "com.scoutfootball.desktop"
    assert "frontend/**/*" in package["build"]["files"]
    assert any(
        resource["to"] == "backend/" for resource in package["build"]["extraResources"]
    )


def test_desktop_build_scripts_copy_runtime_frontend_files_and_data():
    powershell = (PROJECT_ROOT / "scripts" / "build-desktop-windows.ps1").read_text(
        encoding="utf-8"
    )
    shell = (PROJECT_ROOT / "scripts" / "build-desktop.sh").read_text(encoding="utf-8")

    for required_file in ("config.js", "user-guide.html"):
        assert required_file in powershell
        assert required_file in shell

    assert 'Join-Path $FrontendSrc "data"' in powershell
    assert '"$PROJECT_DIR/frontend/data"' in shell


def test_api_status_poll_updates_offline_banner():
    app_js = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert "function syncApiOfflineBanner()" in app_js
    assert "setInterval(checkApiStatus, 10000)" in app_js
    assert app_js.count("syncApiOfflineBanner();") >= 2
    assert "apiOnline !== false || window.__SCOUTFOOTBALL_DESKTOP__" in app_js
