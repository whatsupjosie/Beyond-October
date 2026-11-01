param(
    [string]$DownloadsPath = (Join-Path $env:USERPROFILE "Downloads"),
    [string]$PlaygroundPath = "C:\Users\hardc\OneDrive\Documents\Playground",
    [string]$ReportDir = "C:\Users\hardc\OneDrive\Documents\Playground\codex_reports\zip_inventory_20260609",
    [switch]$MoveSafePlaygroundZipDuplicates
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

function Test-InSpecialFolder {
    param([string]$Path)
    $normalized = $Path.ToLowerInvariant()
    return (
        $normalized -match "\\\.git(\\|$)" -or
        $normalized -match "\\__pycache__(\\|$)" -or
        $normalized -match "\\node_modules(\\|$)" -or
        $normalized -match "\\duplicates(\\|$)"
    )
}

function Get-ZipRelevance {
    param(
        [string]$ZipName,
        [string[]]$Entries
    )
    $haystack = (($ZipName + "`n" + ($Entries -join "`n")).ToLowerInvariant())
    $score = 0
    $hits = New-Object System.Collections.Generic.List[string]
    foreach ($term in @(
        "pubcast", "main.py", "requirements.txt", "system_policy.json",
        "modules/", "static/", "templates/", "tests/", "agent", "orchestrator",
        "llm", "ollama", "avatar", "stage", "studio", "friday", "lunch",
        "whatsupjosie", "little", "buddy", "evo", "memory", "voice", "camera"
    )) {
        if ($haystack.Contains($term)) {
            $score += 1
            $hits.Add($term) | Out-Null
        }
    }
    if ($score -ge 9) { return "high:" + (($hits | Select-Object -First 14) -join ",") }
    if ($score -ge 4) { return "medium:" + (($hits | Select-Object -First 12) -join ",") }
    if ($score -ge 1) { return "low:" + (($hits | Select-Object -First 8) -join ",") }
    return "none"
}

function Get-GitTrackedFiles {
    param([string]$RepoPath)
    $tracked = New-Object "System.Collections.Generic.HashSet[string]"
    if (Test-Path -LiteralPath (Join-Path $RepoPath ".git")) {
        $files = & git -C $RepoPath ls-files 2>$null
        foreach ($file in $files) {
            $full = [System.IO.Path]::GetFullPath((Join-Path $RepoPath $file))
            $tracked.Add($full.ToLowerInvariant()) | Out-Null
        }
    }
    return $tracked
}

New-DirectoryIfMissing -Path $ReportDir

$summaryRows = New-Object System.Collections.Generic.List[object]
$entryRows = New-Object System.Collections.Generic.List[object]
$errorRows = New-Object System.Collections.Generic.List[object]

$roots = @(
    [PSCustomObject]@{ Scope = "Downloads"; Path = $DownloadsPath },
    [PSCustomObject]@{ Scope = "Playground"; Path = $PlaygroundPath }
)

foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root.Path)) {
        $errorRows.Add([PSCustomObject]@{
            Scope = $root.Scope
            ZipPath = $root.Path
            Error = "Root path not found"
        }) | Out-Null
        continue
    }

    $zipFiles = Get-ChildItem -LiteralPath $root.Path -Recurse -Force -File -Filter "*.zip" -ErrorAction SilentlyContinue |
        Where-Object { -not (Test-InSpecialFolder -Path $_.FullName) } |
        Sort-Object FullName

    foreach ($zip in $zipFiles) {
        $hash = $null
        $entryNames = @()
        $entryCount = 0
        $totalUncompressed = 0L
        $topDirs = New-Object "System.Collections.Generic.HashSet[string]"
        $extensions = New-Object "System.Collections.Generic.Dictionary[string,int]"
        try {
            $hash = (Get-FileHash -LiteralPath $zip.FullName -Algorithm SHA256).Hash
            $archive = [System.IO.Compression.ZipFile]::OpenRead($zip.FullName)
            try {
                foreach ($entry in $archive.Entries) {
                    $entryCount += 1
                    $entryNames += $entry.FullName
                    $totalUncompressed += [int64]$entry.Length

                    $cleanName = $entry.FullName.Replace("/", "\")
                    $parts = $cleanName.Split("\", [System.StringSplitOptions]::RemoveEmptyEntries)
                    if ($parts.Count -gt 0) {
                        $topDirs.Add($parts[0]) | Out-Null
                    }
                    $ext = [System.IO.Path]::GetExtension($entry.FullName).ToLowerInvariant()
                    if ([string]::IsNullOrWhiteSpace($ext)) { $ext = "(none)" }
                    if (-not $extensions.ContainsKey($ext)) { $extensions[$ext] = 0 }
                    $extensions[$ext] += 1

                    $entryRows.Add([PSCustomObject]@{
                        Scope = $root.Scope
                        ZipPath = $zip.FullName
                        ZipName = $zip.Name
                        EntryPath = $entry.FullName
                        EntryBytes = $entry.Length
                        CompressedBytes = $entry.CompressedLength
                    }) | Out-Null
                }
            }
            finally {
                $archive.Dispose()
            }

            $topDirText = ($topDirs | Sort-Object | Select-Object -First 12) -join ";"
            $extText = ($extensions.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 14 | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ";"
            $summaryRows.Add([PSCustomObject]@{
                Scope = $root.Scope
                ZipPath = $zip.FullName
                ZipName = $zip.Name
                SizeBytes = $zip.Length
                LastWriteTime = $zip.LastWriteTime
                SHA256 = $hash
                EntryCount = $entryCount
                UncompressedBytes = $totalUncompressed
                TopItems = $topDirText
                ExtensionProfile = $extText
                PubCastRelevance = Get-ZipRelevance -ZipName $zip.Name -Entries $entryNames
            }) | Out-Null
        }
        catch {
            $errorRows.Add([PSCustomObject]@{
                Scope = $root.Scope
                ZipPath = $zip.FullName
                Error = $_.Exception.Message
            }) | Out-Null
        }
    }
}

$summaryCsv = Join-Path $ReportDir "zip_summary.csv"
$entriesCsv = Join-Path $ReportDir "zip_entries.csv"
$errorsCsv = Join-Path $ReportDir "zip_errors.csv"
$duplicatesCsv = Join-Path $ReportDir "zip_duplicates.csv"
$movesCsv = Join-Path $ReportDir "zip_duplicate_moves.csv"
$readme = Join-Path $ReportDir "README.md"

$summaryRows | Export-Csv -NoTypeInformation -Path $summaryCsv
$entryRows | Export-Csv -NoTypeInformation -Path $entriesCsv
$errorRows | Export-Csv -NoTypeInformation -Path $errorsCsv

$duplicateRows = New-Object System.Collections.Generic.List[object]
$moveRows = New-Object System.Collections.Generic.List[object]

$groups = $summaryRows |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_.SHA256) } |
    Group-Object Scope, SHA256 |
    Where-Object { $_.Count -gt 1 }

$playgroundTracked = Get-GitTrackedFiles -RepoPath $PlaygroundPath

foreach ($group in $groups) {
    $items = @($group.Group | Sort-Object LastWriteTime, ZipPath)
    $canonical = $items[0]
    foreach ($item in $items) {
        $isCanonical = ($item.ZipPath -eq $canonical.ZipPath)
        $duplicateRows.Add([PSCustomObject]@{
            Scope = $item.Scope
            SHA256 = $item.SHA256
            KeepCanonical = $canonical.ZipPath
            ZipPath = $item.ZipPath
            IsCanonical = $isCanonical
            SizeBytes = $item.SizeBytes
            EntryCount = $item.EntryCount
            PubCastRelevance = $item.PubCastRelevance
        }) | Out-Null
    }

    if ($MoveSafePlaygroundZipDuplicates -and $canonical.Scope -eq "Playground") {
        foreach ($item in ($items | Where-Object { $_.ZipPath -ne $canonical.ZipPath })) {
            $full = [System.IO.Path]::GetFullPath($item.ZipPath)
            $lower = $full.ToLowerInvariant()
            $insidePlayground = $lower.StartsWith(([System.IO.Path]::GetFullPath($PlaygroundPath)).ToLowerInvariant())
            $isTracked = $playgroundTracked.Contains($lower)
            $isSpecial = Test-InSpecialFolder -Path $full

            if ($insidePlayground -and -not $isTracked -and -not $isSpecial) {
                $sourceFile = Get-Item -LiteralPath $full -ErrorAction Stop
                $sourceDir = $sourceFile.Directory.FullName
                $duplicateDir = Join-Path $sourceDir "duplicates"
                New-DirectoryIfMissing -Path $duplicateDir
                $target = Join-Path $duplicateDir $sourceFile.Name
                if (Test-Path -LiteralPath $target) {
                    $base = [System.IO.Path]::GetFileNameWithoutExtension($sourceFile.Name)
                    $ext = [System.IO.Path]::GetExtension($sourceFile.Name)
                    $target = Join-Path $duplicateDir ($base + "_duplicate_" + (Get-Date -Format "yyyyMMddHHmmss") + $ext)
                }
                Move-Item -LiteralPath $sourceFile.FullName -Destination $target
                $moveRows.Add([PSCustomObject]@{
                    Status = "Moved"
                    SHA256 = $item.SHA256
                    KeepCanonical = $canonical.ZipPath
                    From = $sourceFile.FullName
                    To = $target
                    Reason = "Byte-identical duplicate zip in Playground; untracked; outside special folders"
                }) | Out-Null
            }
            else {
                $moveRows.Add([PSCustomObject]@{
                    Status = "Skipped"
                    SHA256 = $item.SHA256
                    KeepCanonical = $canonical.ZipPath
                    From = $full
                    To = ""
                    Reason = "Safety guard: not inside Playground, tracked by git, or special folder"
                }) | Out-Null
            }
        }
    }
}

$duplicateRows | Export-Csv -NoTypeInformation -Path $duplicatesCsv
$moveRows | Export-Csv -NoTypeInformation -Path $movesCsv

$high = @($summaryRows | Where-Object { $_.PubCastRelevance -like "high:*" }).Count
$medium = @($summaryRows | Where-Object { $_.PubCastRelevance -like "medium:*" }).Count
$low = @($summaryRows | Where-Object { $_.PubCastRelevance -like "low:*" }).Count
$none = @($summaryRows | Where-Object { $_.PubCastRelevance -eq "none" }).Count

$readmeLines = @(
    "# Zip Inventory Report",
    "",
    "Generated: $(Get-Date -Format o)",
    "",
    "- Downloads root: $DownloadsPath",
    "- Playground root: $PlaygroundPath",
    "- Zip summaries: $summaryCsv",
    "- Every zip entry: $entriesCsv",
    "- Zip read errors: $errorsCsv",
    "- Byte-identical duplicate groups: $duplicatesCsv",
    "- Duplicate moves attempted: $movesCsv",
    "",
    "## Counts",
    "",
    "- Total readable zips: $($summaryRows.Count)",
    "- Total zip entries indexed: $($entryRows.Count)",
    "- Zip read errors: $($errorRows.Count)",
    "- High PubCast relevance: $high",
    "- Medium PubCast relevance: $medium",
    "- Low PubCast relevance: $low",
    "- No obvious PubCast relevance: $none",
    "- Duplicate rows: $($duplicateRows.Count)",
    "- Move rows: $($moveRows.Count)"
)

$readmeLines | Set-Content -Path $readme -Encoding UTF8

[PSCustomObject]@{
    ReportDir = $ReportDir
    TotalReadableZips = $summaryRows.Count
    TotalZipEntries = $entryRows.Count
    ZipReadErrors = $errorRows.Count
    DuplicateRows = $duplicateRows.Count
    MoveRows = $moveRows.Count
    HighPubCastRelevance = $high
    MediumPubCastRelevance = $medium
    LowPubCastRelevance = $low
} | Format-List
