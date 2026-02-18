$ErrorActionPreference = "Continue"

$base = "http://localhost:8000/api/v1"
$direct = "http://localhost:8002"
$today = (Get-Date).ToString("yyyy-MM-dd")
$year = (Get-Date).Year
$month = (Get-Date).Month

$results = @()

function Add-Res {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail = ""
    )

    $script:results += [pscustomobject]@{
        Name = $Name
        Status = if ($Ok) { "OK" } else { "FAIL" }
        Detail = $Detail
    }
}

$email = ""
$username = ""
$password = "TestPass123!"
$headers = @{}
$extractionId1 = $null
$extractionId2 = $null

try {
    $email = "e2efull+" + [guid]::NewGuid().ToString("N") + "@example.com"
    $username = "e2e" + (Get-Random -Minimum 1000 -Maximum 9999)

    $registerBody = @{
        email = $email
        username = $username
        password = $password
        full_name = "Journal E2E"
        timezone = "UTC"
    } | ConvertTo-Json

    $register = Invoke-RestMethod -Method Post -Uri "$base/auth/register" -Body $registerBody -ContentType "application/json"
    $token = $register.access_token
    $headers = @{ Authorization = "Bearer $token" }
    Add-Res "auth.register" $true $email
}
catch {
    Add-Res "auth.register" $false $_.Exception.Message
}

try {
    $body = @{
        entry_text = "Slept 7 hours. Walked 5000 steps. Drank 1.5 liters water. Mood 8."
        entry_date = $today
        detect_gaps = $false
        require_complete = $false
    } | ConvertTo-Json

    $resp = Invoke-RestMethod -Method Post -Uri "$base/journal/process" -Headers $headers -Body $body -ContentType "application/json"
    $extractionId1 = $resp.entry_id
    Add-Res "journal.process.valid" $true $extractionId1
}
catch {
    Add-Res "journal.process.valid" $false $_.Exception.Message
}

try {
    $body = @{
        entry_text = "Yesterday was weird, had stuff, met someone, did some work, ate something."
        entry_date = $today
        detect_gaps = $true
        require_complete = $false
    } | ConvertTo-Json

    $resp = Invoke-RestMethod -Method Post -Uri "$base/journal/process" -Headers $headers -Body $body -ContentType "application/json"
    $extractionId2 = $resp.entry_id
    $gapCount = ($resp.clarification_questions | Measure-Object).Count
    Add-Res "journal.process.gaps" $true "entry=$extractionId2 gaps=$gapCount"
}
catch {
    Add-Res "journal.process.gaps" $false $_.Exception.Message
}

try {
    $pending = Invoke-RestMethod -Method Get -Uri "$base/journal/pending-gaps" -Headers $headers
    $count = ($pending | Measure-Object).Count
    Add-Res "journal.pending-gaps" $true "count=$count"

    if ($count -gt 0) {
        try {
            $gapId = $pending[0].gap_id
            $resolveBody = @{
                gap_id = $gapId
                user_response = "It was a 30 minute run in the morning."
            } | ConvertTo-Json

            Invoke-RestMethod -Method Post -Uri "$base/journal/resolve-gap" -Headers $headers -Body $resolveBody -ContentType "application/json" | Out-Null
            Add-Res "journal.resolve-gap" $true $gapId
        }
        catch {
            Add-Res "journal.resolve-gap" $false $_.Exception.Message
        }
    }
    else {
        Add-Res "journal.resolve-gap" $true "no pending gaps"
    }
}
catch {
    Add-Res "journal.pending-gaps" $false $_.Exception.Message
}

try {
    if ($extractionId2) {
        $paragraphBody = @{
            entry_id = $extractionId2
            user_paragraph = "The activity was badminton for 45 minutes at 7am. Breakfast was idli and coffee."
        } | ConvertTo-Json

        Invoke-RestMethod -Method Post -Uri "$base/journal/resolve-paragraph" -Headers $headers -Body $paragraphBody -ContentType "application/json" | Out-Null
        Add-Res "journal.resolve-paragraph" $true $extractionId2
    }
    else {
        Add-Res "journal.resolve-paragraph" $false "missing extraction id"
    }
}
catch {
    Add-Res "journal.resolve-paragraph" $false $_.Exception.Message
}

# journal GET endpoints
$journalGetEndpoints = @(
    "/journal/activities",
    "/journal/activity-summary",
    "/journal/health",
    "/journal/metrics"
)

foreach ($path in $journalGetEndpoints) {
    try {
        Invoke-WebRequest -Method Get -Uri "$base$path" -Headers $headers -UseBasicParsing | Out-Null
        Add-Res "journal$path" $true
    }
    catch {
        Add-Res "journal$path" $false $_.Exception.Message
    }
}

# reporting endpoints from openapi
try {
    $spec = Invoke-RestMethod -Method Get -Uri "$direct/openapi.json"
    $reportPaths = @(
        $spec.paths.PSObject.Properties |
            Where-Object { $_.Name -like "/journal/reports/*" } |
            ForEach-Object { $_.Name } |
            Sort-Object -Unique
    )

    foreach ($path in $reportPaths) {
        try {
            $operation = $spec.paths.$path.get
            if (-not $operation) {
                continue
            }

            $qs = @{}
            if ($operation.parameters) {
                foreach ($parameter in $operation.parameters) {
                    if ($parameter.in -ne "query") {
                        continue
                    }

                    switch ($parameter.name) {
                        "target_date" { $qs[$parameter.name] = $today; break }
                        "start_date" { $qs[$parameter.name] = $today; break }
                        "end_date" { $qs[$parameter.name] = $today; break }
                        "year" { $qs[$parameter.name] = "$year"; break }
                        "month" { $qs[$parameter.name] = "$month"; break }
                        "bucket" { $qs[$parameter.name] = "day"; break }
                        "days" { $qs[$parameter.name] = "7"; break }
                        default {
                            if ($parameter.required) {
                                $qs[$parameter.name] = "1"
                            }
                        }
                    }
                }
            }

            $query = ""
            if ($qs.Keys.Count -gt 0) {
                $pairs = $qs.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }
                $query = "?" + ($pairs -join "&")
            }

            Invoke-WebRequest -Method Get -Uri "$base$path$query" -Headers $headers -UseBasicParsing | Out-Null
            Add-Res "report$path" $true $query
        }
        catch {
            Add-Res "report$path" $false $_.Exception.Message
        }
    }
}
catch {
    Add-Res "report.openapi.enumeration" $false $_.Exception.Message
}

# DB checks
try {
    $uid = docker exec plos-supabase-db psql -U postgres -d plos -t -A -c "SELECT id FROM users WHERE email = '$email' LIMIT 1;"
    $uid = $uid.Trim()
    Add-Res "db.user.lookup" (-not [string]::IsNullOrWhiteSpace($uid)) $uid

    if ($extractionId1) {
        $q = @"
SELECT 'journal_extractions' AS table_name, COUNT(*) FROM journal_extractions WHERE id = '$extractionId1'
UNION ALL
SELECT 'extraction_metrics', COUNT(*) FROM extraction_metrics WHERE extraction_id = '$extractionId1'
UNION ALL
SELECT 'extraction_activities', COUNT(*) FROM extraction_activities WHERE extraction_id = '$extractionId1'
UNION ALL
SELECT 'extraction_consumptions', COUNT(*) FROM extraction_consumptions WHERE extraction_id = '$extractionId1'
UNION ALL
SELECT 'extraction_sleep', COUNT(*) FROM extraction_sleep WHERE extraction_id = '$extractionId1'
UNION ALL
SELECT 'journal_timeseries', COUNT(*) FROM journal_timeseries WHERE extraction_id = '$extractionId1';
"@

        $dbOut = docker exec plos-supabase-db psql -U postgres -d plos -t -A -F ',' -c $q
        Add-Res "db.extraction.rows" $true (($dbOut | Out-String).Trim())
    }
}
catch {
    Add-Res "db.validation" $false $_.Exception.Message
}

$results | Format-Table -AutoSize

$fails = @($results | Where-Object { $_.Status -eq "FAIL" })
Write-Host "TOTAL=$($results.Count) FAILS=$($fails.Count)"

if ($fails.Count -gt 0) {
    exit 1
}

exit 0
