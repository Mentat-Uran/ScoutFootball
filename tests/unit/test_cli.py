from scoutlab.__main__ import render_summary


def test_render_summary_mentions_status_and_modules() -> None:
    summary = render_summary()

    assert "status:" in summary
    assert "modules:" in summary
    assert "adapters" in summary
