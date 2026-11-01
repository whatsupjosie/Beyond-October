param(
    [string]$ReportDir = "C:\Users\hardc\OneDrive\Documents\Playground\codex_reports\zip_inventory_20260609_stream",
    [string]$PlaygroundPath = "C:\Users\hardc\OneDrive\Documents\Playground",
    [switch]$MoveSafeSameFolderPlaygroundDuplicates
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-DirectoryIfMissing {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Test-SpecialPath {
    param([string]$Path)
    $normalized = $Path.ToLowerInvariant()
    return (
        $normalized -match "\\\.git(\\|$)" -or
        $normalized -match "\\__pycache__(\\|$)" -or
        $normalized -match "\\node_modules(\\|$)" -or
        $normalized -match "\\duplicates(\\|$)"
    )
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

function Test-InNestedGitRepo {
    param(
        [string]$FilePath,
        [string]$RootRepoPath
    )
    $dir = Split-Path -Parent $FilePath
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $top = & git -C $dir rev-parse --show-toplevel 2>$null
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($top)) {
        return $false
    }
    $resolvedTop = [System.IO.Path]::GetFullPath([string]$top).TrimEnd("\").ToLowerInvariant()
    $resolvedRoot = [System.IO.Path]::GetFullPath($RootRepoPath).TrimEnd("\").ToLowerInvariant()
    return ($resolvedTop -ne $resolvedRoot)
}

$hashCsv = Join-Path $ReportDir "zip_candidate_hashes_stream.csv"
$duplicatesCsv = Join-Path $ReportDir "zip_exact_duplicates_stream.csv"
$sameFolderCsv = Join-Path $ReportDir "zip_exact_same_folder_duplicates_stream.csv"
$movesCsv = Join-Path $ReportDir "zip_exact_duplicate_moves_stream.csv"

if (-not (Test-Path -LiteralPath $hashCsv)) {
    throw "Missing hash CSV: $hashCsv"
}

$hashRows = Import-Csv -LiteralPath $hashCsv |
    Where-Object { $_.HashStatus -eq "OK" -and -not [string]::IsNullOrWhiteSpace($_.SHA256) }

$duplicateRows = New-Object System.Collections.Generic.List[object]
$sameFolderRows = New-Object System.Collections.Generic.List[object]
$moveRows = New-Object System.Collections.Generic.List[object]

$hashGroups = $hashRows |
    Group-Object Scope, SHA256 |
    Where-Object { $_.Count -gt 1 }

foreach ($group in $hashGroups) {
    $items = @($group.Group | Sort-Object LastWriteTime, ZipPath)
    $canonical = $items[0]
    foreach ($item in $items) {
        $duplicateRows.Add([PSCustomObject]@{
            Scope = $item.Scope
            SHA256 = $item.SHA256
            KeepCanonical = $canonical.ZipPath
            ZipPath = $item.ZipPath
            IsCanonical = ($item.ZipPath -eq $canonical.ZipPath)
            Directory = $item.Directory
            SizeBytes = $item.SizeBytes
            EntryCount = $item.EntryCount
            PubCastRelevance = $item.PubCastRelevance
        }) | Out-Null
    }

    $items | Group-Object Directory | Where-Object { $_.Count -gt 1 } | ForEach-Object {
        $folderItems = @($_.Group | Sort-Object LastWriteTime, ZipPath)
        $folderCanonical = $folderItems[0]
        foreach ($item in $folderItems) {
            $sameFolderRows.Add([PSCustomObject]@{
                Scope = $item.Scope
                SHA256 = $item.SHA256
                Directory = $item.Directory
                KeepCanonical = $folderCanonical.ZipPath
                ZipPath = $item.ZipPath
                IsCanonical = ($item.ZipPath -eq $folderCanonical.ZipPath)
                SizeBytes = $item.SizeBytes
                PubCastRelevance = $item.PubCastRelevance
            }) | Out-Null
        }
    }
}

$duplicateRows | Export-Csv -NoTypeInformation -Path $duplicatesCsv
$sameFolderRows | Export-Csv -NoTypeInformation -Path $sameFolderCsv

if ($MoveSafeSameFolderPlaygroundDuplicates) {
    $tracked = Get-GitTrackedFiles -RepoPath $PlaygroundPath
    $playgroundRoot = [System.IO.Path]::GetFullPath($PlaygroundPath).ToLowerInvariant()
    $sameFolderRows |
        Where-Object { $_.Scope -eq "Playground" -and $_.IsCanonical -eq "False" } |
        ForEach-Object {
            $source = [System.IO.Path]::GetFullPath($_.ZipPath)
            $sourceLower = $source.ToLowerInvariant()
            $insidePlayground = $sourceLower.StartsWith($playgroundRoot)
            $trackedByGit = $tracked.Contains($sourceLower)
            $insideNestedGit = Test-InNestedGitRepo -FilePath $source -RootRepoPath $PlaygroundPath
            $special = Test-SpecialPath -Path $source

            if ($insidePlayground -and -not $trackedByGit -and -not $insideNestedGit -and -not $special -and (Test-Path -LiteralPath $source)) {
                $file = Get-Item -LiteralPath $source
                $targetDir = Join-Path $file.Directory.FullName "duplicates"
                New-DirectoryIfMissing -Path $targetDir
                $target = Join-Path $targetDir $file.Name
                if (Test-Path -LiteralPath $target) {
                    $base = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
                    $ext = [System.IO.Path]::GetExtension($file.Name)
                    $target = Join-Path $targetDir ($base + "_duplicate_" + (Get-Date -Format "yyyyMMddHHmmss") + $ext)
                }
                Move-Item -LiteralPath $file.FullName -Destination $target
                $moveRows.Add([PSCustomObject]@{
                    Status = "Moved"
                    From = $file.FullName
                    To = $target
                    SHA256 = $_.SHA256
                    KeepCanonical = $_.KeepCanonical
                    Reason = "Same-folder byte-identical Playground zip duplicate; untracked; outside special folders"
                }) | Out-Null
            }
            else {
                $moveRows.Add([PSCustomObject]@{
                    Status = "Skipped"
                    From = $source
                    To = ""
                    SHA256 = $_.SHA256
                    KeepCanonical = $_.KeepCanonical
                    Reason = "Safety guard: not inside Playground, tracked by git, nested git repo, special folder, or missing"
                }) | Out-Null
            }
        }
}

$moveRows | Export-Csv -NoTypeInformation -Path $movesCsv

[PSCustomObject]@{
    ExactDuplicateGroups = @($hashGroups).Count
    ExactDuplicateRows = $duplicateRows.Count
    SameFolderDuplicateRows = $sameFolderRows.Count
    MoveRows = $moveRows.Count
    MovedRows = @($moveRows | Where-Object { $_.Status -eq "Moved" }).Count
    SkippedMoveRows = @($moveRows | Where-Object { $_.Status -eq "Skipped" }).Count
    ReportDir = $ReportDir
} | Format-List
