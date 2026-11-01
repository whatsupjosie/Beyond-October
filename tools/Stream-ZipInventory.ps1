param(
    [string]$DownloadsPath = (Join-Path $env:USERPROFILE "Downloads"),
    [string]$PlaygroundPath = "C:\Users\hardc\OneDrive\Documents\Playground",
    [string]$ReportDir = "C:\Users\hardc\OneDrive\Documents\Playground\codex_reports\zip_inventory_20260609_stream",
    [switch]$Resume
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

function New-DirectoryIfMissing {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Test-SkipPath {
    param([string]$Path)
    $normalized = $Path.ToLowerInvariant()
    return (
        $normalized -match "\\\.git(\\|$)" -or
        $normalized -match "\\__pycache__(\\|$)" -or
        $normalized -match "\\node_modules(\\|$)" -or
        $normalized -match "\\duplicates(\\|$)"
    )
}

function ConvertTo-CsvLine {
    param([object[]]$Values)
    $escaped = foreach ($value in $Values) {
        if ($null -eq $value) { $text = "" } else { $text = [string]$value }
        '"' + $text.Replace('"', '""') + '"'
    }
    return ($escaped -join ",")
}

function Get-RelevanceFromText {
    param([string]$Text)
    $haystack = $Text.ToLowerInvariant()
    $hits = New-Object System.Collections.Generic.List[string]
    foreach ($term in @(
        "pubcast", "main.py", "requirements.txt", "system_policy.json",
        "modules/", "static/", "templates/", "tests/", "agent", "orchestrator",
        "llm", "ollama", "avatar", "stage", "studio", "friday", "lunch",
        "whatsupjosie", "little", "buddy", "evo", "memory", "voice", "camera",
        "runtime", "control", "director", "conversation", "response_composer"
    )) {
        if ($haystack.Contains($term)) { $hits.Add($term) | Out-Null }
    }
    $score = $hits.Count
    $hitText = (($hits | Select-Object -First 16) -join ";")
    if ($score -ge 9) { return "high:$hitText" }
    if ($score -ge 4) { return "medium:$hitText" }
    if ($score -ge 1) { return "low:$hitText" }
    return "none"
}

New-DirectoryIfMissing -Path $ReportDir
$summaryCsv = Join-Path $ReportDir "zip_summary.csv"
$entriesCsv = Join-Path $ReportDir "zip_entries.csv"
$errorsCsv = Join-Path $ReportDir "zip_errors.csv"
$processedTxt = Join-Path $ReportDir "processed_paths.txt"
$progressTxt = Join-Path $ReportDir "progress.txt"

if (-not $Resume) {
    ConvertTo-CsvLine @("Scope","ZipPath","ZipName","SizeBytes","LastWriteTime","EntryCount","UncompressedBytes","TopItems","ExtensionProfile","PubCastRelevance") | Set-Content -Path $summaryCsv -Encoding UTF8
    ConvertTo-CsvLine @("Scope","ZipPath","ZipName","EntryPath","EntryBytes","CompressedBytes") | Set-Content -Path $entriesCsv -Encoding UTF8
    ConvertTo-CsvLine @("Scope","ZipPath","Error") | Set-Content -Path $errorsCsv -Encoding UTF8
    "" | Set-Content -Path $processedTxt -Encoding UTF8
    "" | Set-Content -Path $progressTxt -Encoding UTF8
}
else {
    if (-not (Test-Path -LiteralPath $summaryCsv)) {
        ConvertTo-CsvLine @("Scope","ZipPath","ZipName","SizeBytes","LastWriteTime","EntryCount","UncompressedBytes","TopItems","ExtensionProfile","PubCastRelevance") | Set-Content -Path $summaryCsv -Encoding UTF8
    }
    if (-not (Test-Path -LiteralPath $entriesCsv)) {
        ConvertTo-CsvLine @("Scope","ZipPath","ZipName","EntryPath","EntryBytes","CompressedBytes") | Set-Content -Path $entriesCsv -Encoding UTF8
    }
    if (-not (Test-Path -LiteralPath $errorsCsv)) {
        ConvertTo-CsvLine @("Scope","ZipPath","Error") | Set-Content -Path $errorsCsv -Encoding UTF8
    }
    if (-not (Test-Path -LiteralPath $processedTxt)) {
        "" | Set-Content -Path $processedTxt -Encoding UTF8
    }
}

$processed = New-Object "System.Collections.Generic.HashSet[string]"
Get-Content -LiteralPath $processedTxt -ErrorAction SilentlyContinue | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
    $processed.Add($_.ToLowerInvariant()) | Out-Null
}

$summaryWriter = [System.IO.StreamWriter]::new($summaryCsv, $true, [System.Text.UTF8Encoding]::new($false))
$entriesWriter = [System.IO.StreamWriter]::new($entriesCsv, $true, [System.Text.UTF8Encoding]::new($false))
$errorsWriter = [System.IO.StreamWriter]::new($errorsCsv, $true, [System.Text.UTF8Encoding]::new($false))
$processedWriter = [System.IO.StreamWriter]::new($processedTxt, $true, [System.Text.UTF8Encoding]::new($false))

$read = 0
$failed = 0
$skipped = 0
$started = Get-Date

try {
    foreach ($root in @(
        [PSCustomObject]@{ Scope = "Downloads"; Path = $DownloadsPath },
        [PSCustomObject]@{ Scope = "Playground"; Path = $PlaygroundPath }
    )) {
        if (-not (Test-Path -LiteralPath $root.Path)) {
            $errorsWriter.WriteLine((ConvertTo-CsvLine @($root.Scope, $root.Path, "Root path not found")))
            $failed += 1
            continue
        }

        Get-ChildItem -LiteralPath $root.Path -Recurse -Force -File -Filter "*.zip" -ErrorAction SilentlyContinue | ForEach-Object {
            $zip = $_
            if (Test-SkipPath -Path $zip.FullName) { return }
            $zipKey = $zip.FullName.ToLowerInvariant()
            if ($processed.Contains($zipKey)) {
                $skipped += 1
                return
            }

            $entryCount = 0
            $totalUncompressed = 0L
            $topItems = New-Object "System.Collections.Generic.HashSet[string]"
            $extensions = New-Object "System.Collections.Generic.Dictionary[string,int]"
            $relevanceText = $zip.Name + "`n"

            try {
                $archive = [System.IO.Compression.ZipFile]::OpenRead($zip.FullName)
                try {
                    foreach ($entry in $archive.Entries) {
                        $entryCount += 1
                        $totalUncompressed += [int64]$entry.Length
                        $relevanceText += $entry.FullName + "`n"

                        $cleanName = $entry.FullName.Replace("/", "\")
                        $parts = $cleanName.Split("\", [System.StringSplitOptions]::RemoveEmptyEntries)
                        if ($parts.Count -gt 0) { $topItems.Add($parts[0]) | Out-Null }

                        $ext = [System.IO.Path]::GetExtension($entry.FullName).ToLowerInvariant()
                        if ([string]::IsNullOrWhiteSpace($ext)) { $ext = "(none)" }
                        if (-not $extensions.ContainsKey($ext)) { $extensions[$ext] = 0 }
                        $extensions[$ext] += 1

                        $entriesWriter.WriteLine((ConvertTo-CsvLine @($root.Scope, $zip.FullName, $zip.Name, $entry.FullName, $entry.Length, $entry.CompressedLength)))
                    }
                }
                finally {
                    $archive.Dispose()
                }

                $topText = ($topItems | Sort-Object | Select-Object -First 16) -join ";"
                $extText = ($extensions.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 18 | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ";"
                $relevance = Get-RelevanceFromText -Text $relevanceText
                $summaryWriter.WriteLine((ConvertTo-CsvLine @($root.Scope, $zip.FullName, $zip.Name, $zip.Length, $zip.LastWriteTime.ToString("o"), $entryCount, $totalUncompressed, $topText, $extText, $relevance)))
                $processedWriter.WriteLine($zip.FullName)
                $processed.Add($zipKey) | Out-Null
                $read += 1

                if (($read + $failed) % 25 -eq 0) {
                    $summaryWriter.Flush()
                    $entriesWriter.Flush()
                    $errorsWriter.Flush()
                    $processedWriter.Flush()
                    @(
                        "Updated: $(Get-Date -Format o)",
                        "ReadableZipsThisRun=$read",
                        "FailedZipsThisRun=$failed",
                        "SkippedAlreadyProcessed=$skipped",
                        "CurrentZip=$($zip.FullName)",
                        "Started=$($started.ToString("o"))"
                    ) | Set-Content -Path $progressTxt -Encoding UTF8
                }
            }
            catch {
                $errorsWriter.WriteLine((ConvertTo-CsvLine @($root.Scope, $zip.FullName, $_.Exception.Message)))
                $processedWriter.WriteLine($zip.FullName)
                $processed.Add($zipKey) | Out-Null
                $failed += 1
            }
        }
    }
}
finally {
    $summaryWriter.Flush(); $summaryWriter.Dispose()
    $entriesWriter.Flush(); $entriesWriter.Dispose()
    $errorsWriter.Flush(); $errorsWriter.Dispose()
    $processedWriter.Flush(); $processedWriter.Dispose()
    @(
        "Updated: $(Get-Date -Format o)",
        "ReadableZipsThisRun=$read",
        "FailedZipsThisRun=$failed",
        "SkippedAlreadyProcessed=$skipped",
        "Started=$($started.ToString("o"))",
        "FinishedOrInterrupted=$((Get-Date).ToString("o"))"
    ) | Set-Content -Path $progressTxt -Encoding UTF8
}

[PSCustomObject]@{
    ReportDir = $ReportDir
    ReadableZipsThisRun = $read
    FailedZipsThisRun = $failed
    SkippedAlreadyProcessed = $skipped
    Started = $started
    Finished = Get-Date
} | Format-List
