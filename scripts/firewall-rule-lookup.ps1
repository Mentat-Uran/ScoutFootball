function Get-ScoutFootballFirewallRules {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$DisplayName
    )

    $lookupErrors = @()
    try {
        $rules = @(
            Get-NetFirewallRule -DisplayName $DisplayName -ErrorAction SilentlyContinue -ErrorVariable lookupErrors
        )
    } catch {
        throw "Could not query firewall rule '$DisplayName'. $_"
    }

    $notFoundErrors = @(
        $lookupErrors | Where-Object {
            # Get-NetFirewallRule emits this CIM error when a valid query finds no rule.
            $_.CategoryInfo.Category -eq [System.Management.Automation.ErrorCategory]::ObjectNotFound -and
            $_.FullyQualifiedErrorId -eq "CmdletizationQuery_NotFound,Get-NetFirewallRule"
        }
    )
    if (
        $lookupErrors.Count -ne $notFoundErrors.Count -or
        ($lookupErrors.Count -gt 0 -and $rules.Count -gt 0)
    ) {
        throw "Could not query firewall rule '$DisplayName'. $($lookupErrors[0])"
    }

    return $rules
}
