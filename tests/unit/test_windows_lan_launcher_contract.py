from pathlib import Path


def _launcher_files() -> tuple[str, str, str]:
    repository_root = Path(__file__).resolve().parents[2]
    batch = (repository_root / "scripts/start-lan.bat").read_text(encoding="utf-8")
    powershell = (repository_root / "scripts/start-lan.ps1").read_text(encoding="utf-8")
    quickstart = (repository_root / "docs/QUICKSTART.md").read_text(encoding="utf-8")
    return batch, powershell, quickstart


def test_windows_lan_launcher_fails_closed_and_binds_the_detected_private_ip():
    batch, powershell, _ = _launcher_files()
    launcher = f"{batch}\n{powershell}".casefold()

    assert "get-netconnectionprofile" in launcher
    assert 'networkcategory -eq "private"' in launcher
    assert "get-netadapter -physical" in launcher
    assert 'status -eq "up"' in launcher
    for private_ipv4_pattern in (
        r"10(?:\.\d{1,3}){3}",
        r"192\.168(?:\.\d{1,3}){2}",
        r"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.\d{1,3}){2}",
    ):
        assert private_ipv4_pattern in launcher
    assert "serve --host $lanip --port $port" in launcher
    assert "serve --host 0.0.0.0" not in launcher

    no_address_guard = powershell.index("if ([string]::IsNullOrWhiteSpace($lanIp))")
    no_address_exit = powershell.index("exit 1", no_address_guard)
    dependency_sync = powershell.index("& uv sync")
    firewall_rule = powershell.index("New-NetFirewallRule")
    server_start = powershell.index("& uv run python -m scoutfootball serve")
    assert no_address_guard < no_address_exit < dependency_sync < firewall_rule < server_start


def test_windows_lan_firewall_rule_is_scoped_for_new_and_existing_rules():
    _, powershell, _ = _launcher_files()
    assert "Get-NetFirewallRule -DisplayName $ruleName -ErrorAction Stop" in powershell
    existing_block = powershell[
        powershell.index("if ($existingRules.Count -gt 0)") :
        powershell.index("} else {", powershell.index("if ($existingRules.Count -gt 0)"))
    ]
    new_rule_block = powershell[
        powershell.index("New-NetFirewallRule") : powershell.index("} catch {")
    ]

    assert (
        "Set-NetFirewallRule -Enabled True -Direction Inbound "
        "-Action Allow -Profile Private"
    ) in existing_block
    scoped_filter = (
        "Get-NetFirewallAddressFilter |\n"
        "            Set-NetFirewallAddressFilter "
        "-LocalAddress $lanIp -RemoteAddress LocalSubnet"
    )
    assert scoped_filter in existing_block
    assert "Set-NetFirewallPortFilter -Protocol TCP -LocalPort $port" in existing_block
    assert "Could not narrow the existing '$ruleName' firewall rule" in powershell
    assert "refusing to start the LAN server" in powershell

    assert "-LocalAddress $lanIp" in new_rule_block
    assert "-RemoteAddress LocalSubnet" in new_rule_block
    assert "-Profile Private" in new_rule_block
    assert "-Protocol TCP" in new_rule_block
    assert "-LocalPort $port" in new_rule_block


def test_windows_lan_quickstart_documents_narrowed_listener_and_firewall():
    batch, _, quickstart = _launcher_files()

    assert "start-lan.ps1" in batch
    assert "活动物理网卡" in quickstart
    assert "LocalAddress" in quickstart
    assert "RemoteAddress=LocalSubnet" in quickstart
    assert "Private" in quickstart
    assert "没有检测到地址时会停止启动" in quickstart
