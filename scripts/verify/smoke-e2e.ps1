# PLOS Production Smoke Test
# Runs auth + journal + reporting checks through the API gateway.

param(
    [string]$BaseUrl = "http://localhost:8000/api/v1",
    [switch]$RunRateLimitTest,
    [int]$RateLimitRequests = 110,
    [int]$RateLimitThreshold = 100
)

$results = @()

function Add-Result {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Detail = ""
    )
    $script:results += [pscustomobject]@{
        Name = $Name
        Status = $Status
        Detail = $Detail
    }
}

function Expect-Error {
    param(
        [string]$Name,
        [scriptblock]$Action,
        [string]$Expected = "error"
    )
    try {
        & $Action | Out-Null
        Add-Result $Name "FAIL" "expected $Expected"
    } catch {
        Add-Result $Name "OK" "$Expected expected"
    }
}

try {
    $email = "e2e+" + [guid]::NewGuid().ToString("N") + "@example.com"
    $username = "user" + (Get-Random -Minimum 1000 -Maximum 9999)
    $password = "TestPass123!"

    $registerBody = @{ email = $email; username = $username; password = $password; full_name = "E2E User"; timezone = "UTC" } | ConvertTo-Json
    $register = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/register" -Body $registerBody -ContentType "application/json"
    $token = $register.access_token
    Add-Result "auth.register" "OK" "user=$email"

    Expect-Error "auth.register.duplicate" { Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/register" -Body $registerBody -ContentType "application/json" } "400"

    $loginBody = @{ email = $email; password = $password } | ConvertTo-Json
    $login = Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/login" -Body $loginBody -ContentType "application/json"
    $token = $login.access_token
    Add-Result "auth.login" "OK" "token_received"

    $badLoginBody = @{ email = $email; password = "WrongPass123!" } | ConvertTo-Json
    Expect-Error "auth.login.invalid" { Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/login" -Body $badLoginBody -ContentType "application/json" } "401"

    Expect-Error "journal.process.no_token" { Invoke-WebRequest -Method Post -Uri "$BaseUrl/journal/process" -UseBasicParsing } "401"

    $headers = @{ Authorization = "Bearer $token" }
    Invoke-RestMethod -Method Post -Uri "$BaseUrl/auth/verify-token" -Headers $headers | Out-Null
    Add-Result "auth.verify_token" "OK"

    Invoke-WebRequest -Method Get -Uri "$BaseUrl/journal/metrics" -UseBasicParsing | Out-Null
    Add-Result "journal.metrics" "OK"

    $journalBody = @{ entry_text = "Slept 6 hours. Worked 3 hours. Drank 2 liters of water."; entry_date = (Get-Date).ToString("yyyy-MM-dd"); detect_gaps = $false; require_complete = $false } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$BaseUrl/journal/process" -Headers $headers -Body $journalBody -ContentType "application/json" | Out-Null
    Add-Result "journal.process" "OK"

    Expect-Error "journal.process.empty" { Invoke-RestMethod -Method Post -Uri "$BaseUrl/journal/process" -Headers $headers -Body (@{ entry_text = "" } | ConvertTo-Json) -ContentType "application/json" } "422"

    $tooLong = "a" * 10001
    Expect-Error "journal.process.too_long" { Invoke-RestMethod -Method Post -Uri "$BaseUrl/journal/process" -Headers $headers -Body (@{ entry_text = $tooLong } | ConvertTo-Json) -ContentType "application/json" } "422"

    Expect-Error "journal.process.bad_date" { Invoke-RestMethod -Method Post -Uri "$BaseUrl/journal/process" -Headers $headers -Body (@{ entry_text = "test"; entry_date = "2025-13-40" } | ConvertTo-Json) -ContentType "application/json" } "422"

    Invoke-RestMethod -Method Get -Uri "$BaseUrl/journal/reports/weekly-overview" -Headers $headers | Out-Null
    Add-Result "reports.weekly_overview" "OK"

    $today = (Get-Date).ToString("yyyy-MM-dd")
    Invoke-RestMethod -Method Get -Uri "$BaseUrl/journal/reports/daily-overview?target_date=$today" -Headers $headers | Out-Null
    Add-Result "reports.daily_overview" "OK"

    Expect-Error "reports.weekly.invalid_days" { Invoke-WebRequest -Method Get -Uri "$BaseUrl/journal/reports/weekly-overview?days=0" -Headers $headers -UseBasicParsing } "422"

    Expect-Error "reports.monthly.invalid_month" { Invoke-WebRequest -Method Get -Uri "$BaseUrl/journal/reports/monthly-overview?year=2025&month=0" -Headers $headers -UseBasicParsing } "400"

    Expect-Error "reports.range.invalid" { Invoke-WebRequest -Method Get -Uri "$BaseUrl/journal/reports/range-overview?start_date=2025-01-10&end_date=2025-01-01" -Headers $headers -UseBasicParsing } "400"

    Expect-Error "journal.resolve_gap.invalid_id" { Invoke-RestMethod -Method Post -Uri "$BaseUrl/journal/resolve-gap" -Headers $headers -Body (@{ gap_id = "not-a-uuid"; user_response = "ok" } | ConvertTo-Json) -ContentType "application/json" } "422"

    if ($RunRateLimitTest) {
        $hit429 = $false
        for ($i = 1; $i -le $RateLimitRequests; $i++) {
            try {
                Invoke-WebRequest -Method Get -Uri "$BaseUrl/journal/metrics" -UseBasicParsing | Out-Null
            } catch {
                if ($_.Exception.Response -and $_.Exception.Response.StatusCode -eq 429) {
                    $hit429 = $true
                    break
                }
            }
        }
        if ($hit429) {
            Add-Result "rate_limit" "OK" "429 observed"
        } else {
            Add-Result "rate_limit" "WARN" "no 429 observed"
        }
    }

} catch {
    Add-Result "smoke" "FAIL" $_.Exception.Message
}

$results | Format-Table -AutoSize

if ($results | Where-Object { $_.Status -eq "FAIL" }) {
    exit 1
}

exit 0
