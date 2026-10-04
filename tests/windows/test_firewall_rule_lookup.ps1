$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "../../scripts/firewall-rule-lookup.ps1")

$global:FirewallRuleLookupTestMode = "not-found"
function Get-NetFirewallRule {
    [CmdletBinding()]
    param([string]$DisplayName)

    switch ($global:FirewallRuleLookupTestMode) {
        "not-found" {
            $exception = [System.Exception]::new("No matching firewall rule")
            $errorRecord = [System.Management.Automation.ErrorRecord]::new(
                $exception,
                "CmdletizationQuery_NotFound,Get-NetFirewallRule",
                [System.Management.Automation.ErrorCategory]::ObjectNotFound,
                $DisplayName
            )
            $PSCmdlet.WriteError($errorRecord)
        }
        "permission-denied" {
            $exception = [System.Exception]::new("Access denied while querying firewall rules")
            $errorRecord = [System.Management.Automation.ErrorRecord]::new(
                $exception,
                "AccessDenied",
                [System.Management.Automation.ErrorCategory]::PermissionDenied,
                $DisplayName
            )
            $PSCmdlet.WriteError($errorRecord)
        }
        "unexpected-object-not-found" {
            $exception = [System.Exception]::new("Unexpected missing object while querying firewall rules")
            $errorRecord = [System.Management.Automation.ErrorRecord]::new(
                $exception,
                "UnexpectedObjectNotFound,Get-NetFirewallRule",
                [System.Management.Automation.ErrorCategory]::ObjectNotFound,
                $DisplayName
            )
            $PSCmdlet.WriteError($errorRecord)
        }
        "query-failure" {
            throw "CIM query failed"
        }
        "existing" {
            [pscustomobject]@{ DisplayName = $DisplayName }
        }
        default {
            throw "Unexpected test mode: $global:FirewallRuleLookupTestMode"
        }
    }
}

$rules = @(Get-ScoutFootballFirewallRules -DisplayName "ScoutFootball 8000")
if ($rules.Count -ne 0) {
    throw "A missing-rule lookup should return an empty rule list."
}

$global:FirewallRuleLookupTestMode = "existing"
$rules = @(Get-ScoutFootballFirewallRules -DisplayName "ScoutFootball 8000")
if ($rules.Count -ne 1 -or $rules[0].DisplayName -ne "ScoutFootball 8000") {
    throw "An existing rule should be returned by the lookup helper."
}

foreach ($failureMode in @("permission-denied", "unexpected-object-not-found", "query-failure")) {
    $global:FirewallRuleLookupTestMode = $failureMode
    $failedClosed = $false
    try {
        $null = Get-ScoutFootballFirewallRules -DisplayName "ScoutFootball 8000"
    } catch {
        $failedClosed = $_.Exception.Message -like "Could not query firewall rule*"
    }
    if (-not $failedClosed) {
        throw "The $failureMode lookup should fail closed."
    }
}

Write-Host "Firewall rule lookup contract passed."
