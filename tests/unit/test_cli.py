from scoutfootball.__main__ import _cmd_info, build_parser, main


def test_cmd_info_runs(capsys):
    _cmd_info(None)
    out = capsys.readouterr().out
    assert "status:" in out
    assert "modules:" in out
    assert "adapters" in out


def test_main_no_args_shows_help(capsys):
    import sys

    old_argv = sys.argv
    sys.argv = ["scoutfootball"]
    try:
        import pytest

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "scoutfootball" in out.lower()
    finally:
        sys.argv = old_argv


def test_serve_defaults_to_loopback_and_allows_explicit_host():
    parser = build_parser()

    assert parser.parse_args(["serve"]).host == "127.0.0.1"
    assert parser.parse_args(["serve", "--host", "192.0.2.10"]).host == "192.0.2.10"
