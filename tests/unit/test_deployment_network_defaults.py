from pathlib import Path


def test_compose_port_binding_defaults_to_loopback_and_allows_override():
    repository_root = Path(__file__).resolve().parents[2]
    compose = (repository_root / "compose.yaml").read_text(encoding="utf-8")

    assert '"${SCOUTFOOTBALL_BIND_HOST:-127.0.0.1}:8000:8000"' in compose


def test_html_user_guide_uses_loopback_by_default_and_specific_lan_address():
    repository_root = Path(__file__).resolve().parents[2]
    user_guide = (repository_root / "frontend/user-guide.html").read_text(encoding="utf-8")

    assert "serve --host 127.0.0.1 --port 8000" in user_guide
    assert "serve --host 你的电脑IP --port 8000" in user_guide
    assert "serve --host 0.0.0.0 --port 8000" not in user_guide
