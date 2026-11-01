param(
    [string]$ReportDir = "C:\Users\hardc\OneDrive\Documents\Playground\codex_reports\zip_inventory_20260609_stream",
    [switch]$Resume
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertTo-CsvLine {
    param([object[]]$Values)
    $escaped = foreach ($value in $Values) {
        if ($null -eq $value) { $text = "" } else { $text = [string]$value }
        '"' + $text.Replace('"', '""') + '"'
    }
    return ($escaped -join ",")
}

$summaryCsv = Join-Path $ReportDir "zip_summary.csv"
$hashCsv = Join-Path $ReportDir "zip_candidate_hashes_stream.csv"
$progress = Join-Path $ReportDir "duplicate_hash_stream_progress.txt"

if (-not (Test-Path -LiteralPath $summaryCsv)) {
    throw "Missing summary CSV: $summaryCsv"
}

if (-not $Resume -or -not (Test-Path -LiteralPath $hashCsv)) {
    ConvertTo-CsvLine @("Scope","ZipPath","ZipName","Directory","SizeBytes","EntryCount","UncompressedBytes","LastWriteTime","SHA256","PubCastRelevance","HashStatus") |
        Set-Content -Path $hashCsv -Encoding UTF8
}

$alreadyHashed = New-Object "System.Collections.Generic.HashSet[string]"
if (Test-Path -LiteralPath $hashCsv) {
    Import-Csv -LiteralPath $hashCsv | ForEach-Object {
        if ($_.ZipPath) { $alreadyHashed.Add($_.ZipPath.ToLowerInvariant()) | Out-Null }
    }
}

$rows = Import-Csv -LiteralPath $summaryCsv
$candidateGroups = $rows |
    Group-Object Scope, SizeBytes, EntryCount, UncompressedBytes |
    Where-Object { $_.Count -gt 1 }
$candidates = @($candidateGroups | ForEach-Object { $_.Group } | Sort-Object ZipPath -Unique)

$writer = [System.IO.StreamWriter]::new($hashCsv, $true, [System.Text.UTF8Encoding]::new($false))
$hashed = 0
$skipped = 0
$failed = 0
$started = Get-Date

try {
    foreach ($item in $candidates) {
        $key = $item.ZipPath.ToLowerInvariant()
        if ($alreadyHashed.Contains($key)) {
            $skipped += 1
            continue
        }

        $sha = ""
        $status = "OK"
        try {
            $sha = (Get-FileHash -LiteralPath $item.ZipPath -Algorithm SHA256).Hash
            $hashed += 1
        }
        catch {
            $sha = ""
            $status = "ERROR: $($_.Exception.Message)"
            $failed += 1
        }

        $writer.WriteLine((ConvertTo-CsvLine @(
            $item.Scope,
            $item.ZipPath,
            $item.ZipName,
            (Split-Path -Parent $item.ZipPath),
            $item.SizeBytes,
            $item.EntryCount,
            $item.UncompressedBytes,
            $item.LastWriteTime,
            $sha,
            $item.PubCastRelevance,
            $status
        )))
        $alreadyHashed.Add($key) | Out-Null

        if (($hashed + $failed) % 10 -eq 0) {
            $writer.Flush()
            @(
                "Updated: $(Get-Date -Format o)",
                "CandidateTotal=$($candidates.Count)",
                "HashedThisRun=$hashed",
                "FailedThisRun=$failed",
                "SkippedAlreadyHashed=$skipped",
                "TotalRecorded=$($alreadyHashed.Count)",
                "CurrentZip=$($item.ZipPath)",
                "Started=$($started.ToString("o"))"
            ) | Set-Content -Path $progress -Encoding UTF8
        }
    }
}
finally {
    $writer.Flush()
    $writer.Dispose()
    @(
        "Updated: $(Get-Date -Format o)",
        "CandidateTotal=$($candidates.Count)",
        "HashedThisRun=$hashed",
        "FailedThisRun=$failed",
        "SkippedAlreadyHashed=$skipped",
        "TotalRecorded=$($alreadyHashed.Count)",
        "Started=$($started.ToString("o"))",
        "FinishedOrInterrupted=$((Get-Date).ToString("o"))"
    ) | Set-Content -Path $progress -Encoding UTF8
}

[PSCustomObject]@{
    CandidateTotal = $candidates.Count
    HashedThisRun = $hashed
    FailedThisRun = $failed
    SkippedAlreadyHashed = $skipped
    TotalRecorded = $alreadyHashed.Count
    ReportDir = $ReportDir
} | Format-List
