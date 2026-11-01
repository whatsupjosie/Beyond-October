param(
    [string]$ReportDir = "C:\Users\hardc\OneDrive\Documents\Playground\codex_reports\zip_inventory_20260609_stream",
    [string]$OutputMarkdown = "C:\Users\hardc\OneDrive\Documents\Playground\codex_reports\PUBCAST_CLEANUP_AND_PROGRAM_TREE_REPORT.md"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-NormalizedZipFiles {
    param(
        [object[]]$Entries,
        [string]$ZipName
    )
    $zipEntries = @($Entries | Where-Object { $_.ZipName -eq $ZipName })
    if ($zipEntries.Count -eq 0) { return @() }
    $root = (($zipEntries | Select-Object -First 1).EntryPath -split '/')[0]
    @($zipEntries | ForEach-Object {
        $_.EntryPath -replace ('^' + [regex]::Escape($root) + '/'), ''
    } | Where-Object {
        $_ -and
        $_ -notmatch '^\.venv/' -and
        $_ -notmatch '^__pycache__/' -and
        $_ -notmatch '/__pycache__/' -and
        $_ -notmatch '\.pyc$' -and
        $_ -notmatch '/$'
    }) | Sort-Object -Unique
}

function Format-Tree {
    param([string[]]$Paths)
    $lines = New-Object System.Collections.Generic.List[string]
    $dirs = New-Object "System.Collections.Generic.HashSet[string]"
    foreach ($path in $Paths) {
        $parts = $path -split '/'
        if ($parts.Count -gt 1) {
            $running = ""
            for ($i = 0; $i -lt $parts.Count - 1; $i++) {
                $running = if ($running) { "$running/$($parts[$i])" } else { $parts[$i] }
                $dirs.Add($running) | Out-Null
            }
        }
    }

    foreach ($dir in ($dirs | Sort-Object)) {
        $depth = (($dir -split '/').Count - 1)
        $name = ($dir -split '/')[-1]
        $lines.Add(("  " * $depth) + "$name/") | Out-Null
        $prefix = "$dir/"
        $children = $Paths | Where-Object {
            $_.StartsWith($prefix) -and (($_.Substring($prefix.Length)) -notmatch '/')
        } | Sort-Object
        foreach ($child in $children) {
            $lines.Add(("  " * ($depth + 1)) + ($child.Substring($prefix.Length))) | Out-Null
        }
    }

    foreach ($file in ($Paths | Where-Object { $_ -notmatch '/' } | Sort-Object)) {
        $lines.Insert(0, $file)
    }
    return $lines
}

$summary = Import-Csv (Join-Path $ReportDir "zip_summary.csv")
$entries = Import-Csv (Join-Path $ReportDir "zip_entries.csv")
$hashes = Import-Csv (Join-Path $ReportDir "zip_candidate_hashes_stream.csv")
$moves = Import-Csv (Join-Path $ReportDir "zip_exact_duplicate_moves_stream.csv")
$exactDuplicates = Import-Csv (Join-Path $ReportDir "zip_exact_duplicates_stream.csv")

$lunch = Get-NormalizedZipFiles -Entries $entries -ZipName "friday-Lunch.zip"
$main = Get-NormalizedZipFiles -Entries $entries -ZipName "friday-main (4).zip"
$further = Get-NormalizedZipFiles -Entries $entries -ZipName "friday-whatsupjosie-further-better.zip"
$furtherBuild = @($further | Where-Object { $_.StartsWith("pubcast_ai_complete/pubcast_build/") } | ForEach-Object {
    $_ -replace '^pubcast_ai_complete/pubcast_build/', ''
})

$recommended = @($lunch + $furtherBuild) |
    Where-Object {
        $_ -and
        $_ -notmatch '\.zip$' -and
        $_ -notmatch '\.blend$' -and
        $_ -notmatch '\.glb$'
    } |
    Sort-Object -Unique

$assetCandidates = @($lunch + $furtherBuild) |
    Where-Object { $_ -match '\.(glb|blend)$' } |
    Sort-Object -Unique

$archiveCandidates = @($lunch + $furtherBuild) |
    Where-Object { $_ -match '\.zip$' } |
    Sort-Object -Unique

$variantRows = foreach ($zip in @(
    "friday-Lunch.zip",
    "friday-Lunch (1).zip",
    "friday-whatsupjosie-further-better.zip",
    "friday-whatsupjosie-little-buddy.zip",
    "friday-main (4).zip",
    "friday-main (1).zip",
    "friday-main.zip"
)) {
    $files = Get-NormalizedZipFiles -Entries $entries -ZipName $zip
    $hashRow = $hashes | Where-Object { $_.ZipName -eq $zip } | Select-Object -First 1
    $hash = if ($null -ne $hashRow) { $hashRow.SHA256 } else { "" }
    [PSCustomObject]@{
        Zip = $zip
        CleanFiles = $files.Count
        SHA256 = $hash
    }
}

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# PubCast Cleanup And Program Tree Report") | Out-Null
$lines.Add("") | Out-Null
$lines.Add("Generated: $(Get-Date -Format o)") | Out-Null
$lines.Add("") | Out-Null
$lines.Add("## Inventory Status") | Out-Null
$lines.Add("") | Out-Null
$lines.Add("- Readable zips indexed: $($summary.Count)") | Out-Null
$lines.Add("- Zip read errors: $((Import-Csv (Join-Path $ReportDir 'zip_errors.csv')).Count)") | Out-Null
$lines.Add("- Exact duplicate rows proved by SHA256: $($exactDuplicates.Count)") | Out-Null
$lines.Add("- Safe same-folder Playground duplicates moved: $(@($moves | Where-Object { $_.Status -eq 'Moved' }).Count)") | Out-Null
$lines.Add("- Downloads duplicates were reported only, not moved by this session.") | Out-Null
$lines.Add("") | Out-Null
$lines.Add("## Friday Source Comparison") | Out-Null
$lines.Add("") | Out-Null
$lines.Add("| Zip | Clean file count | SHA256 if hashed |") | Out-Null
$lines.Add("| --- | ---: | --- |") | Out-Null
foreach ($row in $variantRows) {
    $lines.Add("| $($row.Zip) | $($row.CleanFiles) | $($row.SHA256) |") | Out-Null
}
$lines.Add("") | Out-Null
$lines.Add('Interpretation: `friday-main (4).zip` appears to be the local GitHub-main download. `friday-Lunch.zip` is a superset of that clean source with 22 additional program/support files. `friday-whatsupjosie-further-better.zip` carries a nested `pubcast_ai_complete/pubcast_build/` build that overlaps with the Lunch extras.') | Out-Null
$lines.Add("") | Out-Null
$lines.Add("## Recommended Clean Program Tree") | Out-Null
$lines.Add("") | Out-Null
$lines.Add('This excludes `.venv`, `__pycache__`, `.pyc`, duplicate source zips, and package/archive zips. Binary art assets are listed separately below.') | Out-Null
$lines.Add("") | Out-Null
$lines.Add('```text') | Out-Null
foreach ($line in (Format-Tree -Paths $recommended)) { $lines.Add($line) | Out-Null }
$lines.Add('```') | Out-Null
$lines.Add("") | Out-Null
$lines.Add("## Asset Candidates To Keep With Program") | Out-Null
$lines.Add("") | Out-Null
foreach ($asset in $assetCandidates) { $lines.Add("- $asset") | Out-Null }
$lines.Add("") | Out-Null
$lines.Add("## Archive Zips To Keep As Source Evidence, Not Program Runtime Files") | Out-Null
$lines.Add("") | Out-Null
foreach ($archive in $archiveCandidates) { $lines.Add("- $archive") | Out-Null }
$lines.Add("") | Out-Null
$lines.Add("## Report Files") | Out-Null
$lines.Add("") | Out-Null
$lines.Add("- Zip summary: $ReportDir\zip_summary.csv") | Out-Null
$lines.Add("- Every zip entry: $ReportDir\zip_entries.csv") | Out-Null
$lines.Add("- Exact duplicates: $ReportDir\zip_exact_duplicates_stream.csv") | Out-Null
$lines.Add("- Same-folder duplicates: $ReportDir\zip_exact_same_folder_duplicates_stream.csv") | Out-Null
$lines.Add("- Move log: $ReportDir\zip_exact_duplicate_moves_stream.csv") | Out-Null

$lines | Set-Content -Path $OutputMarkdown -Encoding UTF8

[PSCustomObject]@{
    OutputMarkdown = $OutputMarkdown
    RecommendedProgramFiles = $recommended.Count
    AssetCandidates = $assetCandidates.Count
    ArchiveCandidates = $archiveCandidates.Count
    SafeDuplicateMoves = @($moves | Where-Object { $_.Status -eq "Moved" }).Count
} | Format-List
