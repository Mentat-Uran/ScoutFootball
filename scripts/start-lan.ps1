$ErrorActionPreference = "Stop"

$portText = $env:SCOUTFOOTBALL_LAN_PORT
if ($portText -notmatch '^[0-9]{1,5}$') {
    Write-Error "Port must be an integer from 1 to 65535." -ErrorAction Continue
    exit 2
}
$port = [int]$portText
if ($port -lt 1 -or $port -gt 65535) {
    Write-Error "Port must be an integer from 1 to 65535." -ErrorAction Continue
    exit 2
}

$privateInterfaceIndices = @(
    Get-NetConnectionProfile -ErrorAction SilentlyContinue |
        Where-Object { $_.NetworkCategory -eq "Private" } |
        Select-Object -ExpandProperty InterfaceIndex
)
$physicalInterfaceIndices = @(
    Get-NetAdapter -Physical -ErrorAction SilentlyContinue |
        Where-Object { $_.Status -eq "Up" } |
        Select-Object -ExpandProperty InterfaceIndex
)
$lanIp = Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred -ErrorAction SilentlyContinue |
    Where-Object {
        $_.InterfaceIndex -in $privateInterfaceIndices -and
        $_.InterfaceIndex -in $physicalInterfaceIndices -and
        $_.IPAddress -match '^(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.\d{1,3}){2})$'
    } |
    Sort-Object -Property InterfaceIndex, IPAddress |
    Select-Object -First 1 -ExpandProperty IPAddress

if ([string]::IsNullOrWhiteSpace($lanIp)) {
    Write-Error "No private IPv4 address on an active physical interface with a Private network profile was detected; refusing to start the LAN server." -ErrorAction Continue
    exit 1
}

$repositoryRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repositoryRoot

Write-Host "=========================================="
Write-Host "  ScoutFootball LAN Deployment"
Write-Host "=========================================="
Write-Host "Port: $port"
Write-Host "Binding to private LAN address: $lanIp"
Write-Host "Open locally and from trusted LAN: http://${lanIp}:$port"
Write-Host "API docs: http://${lanIp}:$port/docs"
Write-Host ""

Write-Host "Ensuring dependencies are ready..."
& uv sync
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$ruleName = "ScoutFootball $port"
$existingRules = @(
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction Stop
)

try {
    if ($existingRules.Count -gt 0) {
        $existingRules |
            Set-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -Profile Private
        $existingRules |
            Get-NetFirewallAddressFilter |
            Set-NetFirewallAddressFilter -LocalAddress $lanIp -RemoteAddress LocalSubnet
        $existingRules |
            Get-NetFirewallPortFilter |
            Set-NetFirewallPortFilter -Protocol TCP -LocalPort $port
    } else {
        New-NetFirewallRule `
            -DisplayName $ruleName `
            -Direction Inbound `
            -Action Allow `
            -Enabled True `
            -Protocol TCP `
            -LocalPort $port `
            -LocalAddress $lanIp `
            -RemoteAddress LocalSubnet `
            -Profile Private | Out-Null
    }
} catch {
    if ($existingRules.Count -gt 0) {
        Write-Error "Could not narrow the existing '$ruleName' firewall rule; refusing to start the LAN server. $_"
        exit 1
    }
    Write-Warning "Could not add the scoped firewall rule. You may need to allow TCP port $port on LocalAddress $lanIp from LocalSubnet with the Private profile. $_"
}

Write-Host "Starting server on ${lanIp}:$port ..."
& uv run python -m scoutfootball serve --host $lanIp --port $port
exit $LASTEXITCODE
