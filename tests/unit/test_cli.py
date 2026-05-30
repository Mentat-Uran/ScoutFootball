from scoutlab.__main__ import _cmd_info, main


def test_cmd_info_runs(capsys):
    _cmd_info(None)
    out = capsys.readouterr().out
    assert "status:" in out
    assert "modules:" in out
    assert "adapters" in out


def test_main_no_args_shows_help(capsys):
    import sys

    old_argv = sys.argv
    sys.argv = ["scoutlab"]
    try:
        import pytest

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "scoutlab" in out.lower()
    finally:
        sys.argv = old_argv
