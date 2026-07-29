<#
.SYNOPSIS
    PRS-0 rating fast gate: runs the rating-system core unit tests in a few
    minutes. Intended for the daily research iteration loop.

.DESCRIPTION
    Covers schema, identity, manifest, contract-quality, model admission,
    research health, rating feature matrix, candidate artifacts, optimizer
    gates and architecture capability registry. Excludes integration, slow
    and e2e tests by design — those run in the full suite.

    PRS-0 R-006 (PLAYER_RATING_RESEARCH_SYSTEM_PLAN.md section 12.2):
    maintainers should get trustworthy feedback on rating-system changes in
    minutes, not the full multi-minute suite. This script is the canonical
    "did I break the rating system?" command.

.NOTES
    Exit code 0 = pass, non-zero = fail. Ruff is included as a static gate
    so a lint breakage cannot be deferred to CI.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path -Parent -Path (Split-Path -Parent -Path $MyInvocation.MyCommand.Path))

Write-Host "==> Ruff (rating-relevant sources)" -ForegroundColor Cyan
uv run ruff check `
    src/scoutfootball/evaluation `
    src/scoutfootball/api.py `
    src/scoutfootball/api_server.py `
    src/scoutfootball/__main__.py `
    src/scoutfootball/architecture.py `
    src/scoutfootball/config.py `
    src/scoutfootball/storage `
    tests/unit/test_research_health.py `
    tests/unit/test_detailed_health.py `
    tests/unit/test_model_admission.py `
    tests/unit/test_truth_labels.py `
    tests/unit/test_source_health.py `
    tests/unit/test_rating_feature_matrix.py `
    tests/unit/test_dataset_manifest.py `
    tests/unit/test_contract_quality.py `
    tests/unit/test_model_run_lifecycle.py `
    tests/unit/test_model_run_registry.py `
    tests/unit/test_candidate_rating_artifact.py `
    tests/unit/test_optimizer_validation_gate.py `
    tests/unit/test_rating_optimizer_validation.py `
    tests/unit/test_rating_regression.py `
    tests/unit/test_reep_identity.py `
    tests/unit/test_transfermarkt_identity.py `
    tests/unit/test_data_contracts.py `
    tests/unit/test_architecture.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: ruff reported issues" -ForegroundColor Red
    exit 1
}

Write-Host "==> pytest rating fast gate" -ForegroundColor Cyan
uv run pytest `
    tests/unit/test_research_health.py `
    tests/unit/test_detailed_health.py `
    tests/unit/test_model_admission.py `
    tests/unit/test_truth_labels.py `
    tests/unit/test_source_health.py `
    tests/unit/test_rating_feature_matrix.py `
    tests/unit/test_dataset_manifest.py `
    tests/unit/test_contract_quality.py `
    tests/unit/test_model_run_lifecycle.py `
    tests/unit/test_model_run_registry.py `
    tests/unit/test_candidate_rating_artifact.py `
    tests/unit/test_optimizer_validation_gate.py `
    tests/unit/test_rating_optimizer_validation.py `
    tests/unit/test_rating_regression.py `
    tests/unit/test_reep_identity.py `
    tests/unit/test_transfermarkt_identity.py `
    tests/unit/test_data_contracts.py `
    tests/unit/test_architecture.py `
    -q `
    -p no:cacheprovider
if ($LASTEXITCODE -ne 0) {
    Write-Host "FAIL: rating fast gate tests failed" -ForegroundColor Red
    exit 1
}

Write-Host "PASS: rating fast gate" -ForegroundColor Green
exit 0
