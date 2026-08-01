"""Contracts for World Cup expected-callup role-depth comparisons."""

from scoutfootball.api import get_wc_squad_balance_comparison


def test_comparison_exposes_role_counts_without_claiming_role_superiority() -> None:
    result = get_wc_squad_balance_comparison("Argentina", "France")

    assert result["status"] == "ok"
    assert result["schema"] == "scoutfootball.world-cup-squad-balance-comparison"
    assert result["scope"] == "expected_callup_snapshot"
    assert len(result["roles"]) == 8
    assert result["roles"][0]["role"] == "GK"
    assert "not a confirmed roster" in result["disclaimer"]
    assert "stronger in a role" in result["disclaimer"]


def test_comparison_reports_an_error_for_unknown_team() -> None:
    result = get_wc_squad_balance_comparison("Argentina", "No Such Team")

    assert result["status"] == "error"
    assert "No Such Team" in result["error"]
