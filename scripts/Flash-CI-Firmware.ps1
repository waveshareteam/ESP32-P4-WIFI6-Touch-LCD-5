[CmdletBinding()]
param(
    [string]$Port = '',
    [int]$Baud = 0,
    [switch]$ListOnly,
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = 'waveshareteam/ESP32-P4-WIFI6-Touch-LCD-5'
$Board = 'ESP32-P4-WIFI6-Touch-LCD-5'
$Chip = 'esp32p4'
$FlashLimit = 32MB
$DefaultStartIndex = 1
$SafeBefore = @('default_reset', 'no_reset')
$SafeAfter = @('hard_reset', 'soft_reset', 'no_reset')
$Projects = @(
    'examples/esp-idf/01_HowToCreateProject', 'examples/esp-idf/02_HelloWorld',
    'examples/esp-idf/03_i2c_tools', 'examples/esp-idf/04_wifistation',
    'examples/esp-idf/05_sdmmc', 'examples/esp-idf/06_I2SCodec',
    'examples/esp-idf/07_Displaycolorbar', 'examples/esp-idf/08_lvgl_demo_v9',
    'examples/esp-idf/09_video_lcd_display', 'examples/esp-idf/10_mp4_player',
    'examples/esp-idf/11_esp_brookesia_phone', 'examples/esp-idf/12_usb_extend_screen'
)
$Items = @()
$index = 1
foreach ($project in $Projects) {
    $slug = (($project.Split('/')[-1].ToLowerInvariant() -replace '[^a-z0-9]+', '-').Trim('-'))
    foreach ($version in @('v5.5.5', 'v6.0.2')) {
        $Items += [pscustomobject]@{ Index = $index; Workflow = 'esp-idf-examples.yml'; Artifact = "firmware-esp-idf-$slug-$version"; Framework = 'esp-idf'; Version = $version; SourceProject = $project }
        $index++
    }
}

function Test-Port([string]$Value) { return $Value -match '^COM\d+$' }
function Test-RelativePackagePath([string]$PackageRoot, [string]$RelativePath) {
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or [System.IO.Path]::IsPathRooted($RelativePath) -or $RelativePath -match '^[A-Za-z]:') { return $false }
    $root = [System.IO.Path]::GetFullPath($PackageRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $PackageRoot $RelativePath))
    return $candidate.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)
}
function Get-NextProgress([int]$CurrentIndex, [int[]]$ConfirmedIndexes, [int]$ItemCount) {
    if ($CurrentIndex -lt 1 -or $CurrentIndex -gt $ItemCount) { throw 'Progress index is outside the item range.' }
    $confirmed = @($ConfirmedIndexes + $CurrentIndex | Where-Object { $_ -ge 1 -and $_ -le $ItemCount } | Sort-Object -Unique)
    return [pscustomobject]@{ CurrentIndex = if ($CurrentIndex -eq $ItemCount) { $CurrentIndex } else { $CurrentIndex + 1 }; ConfirmedIndexes = $confirmed; Completed = ($CurrentIndex -eq $ItemCount) }
}
function Get-StateForFinalSha($Saved, [string]$ExpectedSha) {
    if (-not $Saved -or -not $Saved.PSObject.Properties['FinalSha'] -or -not $Saved.PSObject.Properties['CurrentIndex'] -or -not $Saved.PSObject.Properties['ConfirmedIndexes'] -or [string]$Saved.FinalSha -ne $ExpectedSha) {
        return [pscustomobject]@{ CurrentIndex = $DefaultStartIndex; ConfirmedIndexes = @() }
    }
    $current = [int]$Saved.CurrentIndex
    if ($current -lt 1 -or $current -gt $Items.Count) { return [pscustomobject]@{ CurrentIndex = $DefaultStartIndex; ConfirmedIndexes = @() } }
    $confirmed = @($Saved.ConfirmedIndexes | ForEach-Object { [int]$_ } | Where-Object { $_ -ge 1 -and $_ -le $Items.Count } | Sort-Object -Unique)
    $expected = if ($current -eq $Items.Count -and $confirmed -contains $Items.Count) { @(1..$Items.Count) } elseif ($current -eq 1) { @() } else { @(1..($current - 1)) }
    if (@($confirmed).Count -ne @($expected).Count -or @($confirmed | Where-Object { $_ -notin $expected }).Count -ne 0) { return [pscustomobject]@{ CurrentIndex = $DefaultStartIndex; ConfirmedIndexes = @() } }
    return [pscustomobject]@{ CurrentIndex = $current; ConfirmedIndexes = $confirmed }
}
function Test-CompletedState($State) {
    return $State -and $State.CurrentIndex -eq $Items.Count -and @($State.ConfirmedIndexes | Sort-Object -Unique).Count -eq $Items.Count -and @($State.ConfirmedIndexes | Where-Object { $_ -notin @(1..$Items.Count) }).Count -eq 0
}
function Get-FileSha256([string]$Path) {
    $stream = $null; $algorithm = $null
    try { $stream = [System.IO.File]::OpenRead($Path); $algorithm = [System.Security.Cryptography.SHA256]::Create(); return [System.BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { if ($null -ne $stream) { $stream.Dispose() }; if ($null -ne $algorithm) { $algorithm.Dispose() } }
}

if ($SelfTest) {
    if ($Items.Count -ne 24) { throw 'SelfTest expected exactly 24 ESP-IDF items.' }
    $current = 1; $confirmed = @(); $transitions = 0
    while ($current -lt $Items.Count) { $next = Get-NextProgress $current $confirmed $Items.Count; if ($next.Completed -or $next.CurrentIndex -ne ($current + 1)) { throw 'SelfTest progress transition failed.' }; $current = $next.CurrentIndex; $confirmed = @($next.ConfirmedIndexes); $transitions++ }
    $last = Get-NextProgress $current $confirmed $Items.Count
    if (-not $last.Completed -or @($last.ConfirmedIndexes).Count -ne 24) { throw 'SelfTest did not complete all items.' }
    $reset = Get-StateForFinalSha ([pscustomobject]@{ FinalSha = 'other'; CurrentIndex = 4; ConfirmedIndexes = @(1,2,3) }) ('a' * 40)
    if ($reset.CurrentIndex -ne 1 -or @($reset.ConfirmedIndexes).Count -ne 0) { throw 'SelfTest SHA reset failed.' }
    $complete = Get-StateForFinalSha ([pscustomobject]@{ FinalSha = ('a' * 40); CurrentIndex = 24; ConfirmedIndexes = @(1..24) }) ('a' * 40)
    if (-not (Test-CompletedState $complete)) { throw 'SelfTest completed-state recovery failed.' }
    if ((Test-RelativePackagePath 'C:\package' '..\escape.bin') -or (Test-RelativePackagePath 'C:\package' 'C:\escape.bin') -or -not (Test-RelativePackagePath 'C:\package' 'bin\app.bin')) { throw 'SelfTest path boundary failed.' }
    Write-Output 'SELF_TEST_OK items=24 transitions=23 sha_reset=ok completed_recovery=ok path_boundary=ok'
    return
}
if ($ListOnly) {
    Write-Output 'finalSHA=resolved-at-runtime'
    Write-Output 'port=must-be-explicit-in-normal-mode'
    Write-Output "items=$($Items.Count)"
    foreach ($item in $Items) { Write-Output ('{0}: workflow={1} artifact={2} source={3}' -f $item.Index, $item.Workflow, $item.Artifact, $item.SourceProject) }
    return
}
if ([string]::IsNullOrWhiteSpace($Port)) { throw 'Port is required in normal mode; pass -Port COMx.' }
$Port = $Port.Trim().ToUpperInvariant()
if (-not (Test-Port $Port)) { throw 'Port must be COM followed by digits, for example COMx.' }
if ($Baud -lt 0) { throw 'Baud must be positive when supplied.' }

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$StateRoot = Join-Path $env:LOCALAPPDATA 'Waveshare\ESP32-P4-WIFI6-Touch-LCD-5\ci-firmware'
$StatePath = Join-Path $StateRoot 'state-v1.json'
function Resolve-Executable([string]$Name, [string[]]$Fallbacks) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command -and $command.Source) { return $command.Source }
    foreach ($candidate in $Fallbacks) { if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate } }
    throw "$Name was not found on PATH or in supported fallback locations."
}
function Resolve-Git { return Resolve-Executable 'git' @((Join-Path ${env:ProgramFiles} 'Git\cmd\git.exe'), 'C:\Git\cmd\git.exe', 'D:\Git\cmd\git.exe') }
function Resolve-Gh { return Resolve-Executable 'gh' @((Join-Path ${env:ProgramFiles} 'GitHub CLI\gh.exe')) }
function Resolve-PythonWithEsptool {
    $python = Resolve-Executable 'python' @()
    & $python -c 'import esptool' *> $null
    if ($LASTEXITCODE -ne 0) { throw 'python is present but does not provide esptool.' }
    return $python
}
function Resolve-FinalSha([string]$GitExe) {
    $sha = (& $GitExe -C $RepoRoot rev-parse HEAD 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $sha -notmatch '^[0-9a-fA-F]{40}$') { throw 'Unable to resolve complete local HEAD SHA.' }
    return $sha.ToLowerInvariant()
}
function Assert-CleanBranch([string]$GitExe) {
    $status = (& $GitExe -C $RepoRoot status --porcelain=v1 --untracked-files=all 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or -not [string]::IsNullOrWhiteSpace($status)) { throw 'Refusing to continue: working tree is not clean.' }
    $branch = (& $GitExe -C $RepoRoot symbolic-ref --quiet --short HEAD 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) { throw 'Refusing to continue: check out a non-detached branch first.' }
    return $branch
}
function Assert-ReadyPullRequest([string]$GhExe, [string]$Branch, [string]$FinalSha) {
    $raw = (& $GhExe pr list --repo $Repo --head $Branch --state open --limit 2 --json number,state,isDraft,headRefName,headRefOid 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to query the open pull request.' }
    $prs = @($raw | ConvertFrom-Json)
    if ($prs.Count -ne 1 -or [bool]$prs[0].isDraft -or [string]$prs[0].state -ine 'OPEN' -or [string]$prs[0].headRefName -ne $Branch -or [string]$prs[0].headRefOid -notmatch '^[0-9a-fA-F]{40}$' -or -not [string]::Equals([string]$prs[0].headRefOid, $FinalSha, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing to continue: require one open non-draft PR whose exact head is local HEAD.' }
}
function Resolve-ArtifactRun([string]$GhExe, [string]$FinalSha) {
    $raw = (& $GhExe run list --repo $Repo --workflow 'esp-idf-examples.yml' --commit $FinalSha --status success --limit 20 --json databaseId,headSha,conclusion,createdAt 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to list successful ESP-IDF workflow runs.' }
    $runs = @($raw | ConvertFrom-Json | Where-Object { $_.headSha -eq $FinalSha -and $_.conclusion -eq 'success' } | Sort-Object createdAt -Descending)
    if ($runs.Count -lt 1) { throw 'No successful ESP-IDF workflow run exists for the exact local HEAD SHA.' }
    return [string]$runs[0].databaseId
}
function Read-State([string]$FinalSha) { $saved = if (Test-Path -LiteralPath $StatePath) { Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json } else { $null }; return Get-StateForFinalSha $saved $FinalSha }
function Save-State([int]$CurrentIndex, [int[]]$ConfirmedIndexes, [string]$FinalSha) { if (-not (Test-Path -LiteralPath $StateRoot)) { New-Item -ItemType Directory -Path $StateRoot | Out-Null }; [pscustomobject]@{ FinalSha = $FinalSha; CurrentIndex = $CurrentIndex; ConfirmedIndexes = @($ConfirmedIndexes | Sort-Object -Unique); UpdatedAt = (Get-Date).ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8 }
function Test-ManifestFlashArguments($Flash) {
    if (-not $Flash.PSObject.Properties['extra_esptool_args'] -or -not $Flash.PSObject.Properties['write_flash_args']) { throw 'Package manifest omits structured ESP-IDF flash arguments.' }
    $extra = $Flash.extra_esptool_args
    $names = @($extra.PSObject.Properties.Name)
    if (@($names).Count -ne 4 -or @($names | Where-Object { $_ -notin @('chip', 'before', 'after', 'stub') }).Count -ne 0 -or [string]$extra.chip -ne $Chip -or [string]$extra.before -notin $SafeBefore -or [string]$extra.after -notin $SafeAfter -or $extra.stub -isnot [bool]) { throw 'Package manifest has unsafe global ESP-IDF flash arguments.' }
    $groups = @{}; $write = @()
    foreach ($entry in @($Flash.write_flash_args)) {
        $option = [string]$entry.option; $value = [string]$entry.value
        $group = switch ($option) { '--flash_mode' { 'mode' } '--flash-mode' { 'mode' } '--flash_size' { 'size' } '--flash-size' { 'size' } '--flash_freq' { 'freq' } '--flash-freq' { 'freq' } default { throw "Package manifest has unsafe write_flash option: $option" } }
        $allowed = switch ($group) { 'mode' { @('qio', 'qout', 'dio', 'dout', 'keep') } 'size' { @('keep', 'detect', '1MB', '2MB', '4MB', '8MB', '16MB', '32MB') } 'freq' { @('keep', '20m', '26m', '40m', '80m') } }
        if ($groups.ContainsKey($group) -or $value -notin $allowed) { throw "Package manifest has unsafe or duplicate write_flash option: $option" }
        $groups[$group] = $true; $write += @($option, $value)
    }
    if (@($groups.Keys).Count -ne 3 -or @($groups.Keys | Where-Object { $_ -notin @('mode', 'size', 'freq') }).Count -ne 0) { throw 'Package manifest must contain exactly mode, size, and freq write_flash arguments.' }
    return [pscustomobject]@{ Before = [string]$extra.before; After = [string]$extra.after; Stub = [bool]$extra.stub; WriteFlashArgs = $write }
}
function Test-PackageManifest([string]$PackageDir, $Item, [string]$FinalSha) {
    $manifestPath = Join-Path $PackageDir 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'Package manifest.json is missing.' }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema_version -ne 1 -or $manifest.board -ne $Board -or $manifest.chip -ne $Chip -or $manifest.framework -ne $Item.Framework -or $manifest.framework_version -ne $Item.Version -or $manifest.source_project -ne $Item.SourceProject -or $manifest.git_sha -notmatch '^[0-9a-fA-F]{40}$' -or -not [string]::Equals([string]$manifest.git_sha, $FinalSha, [System.StringComparison]::OrdinalIgnoreCase) -or [int64]$manifest.flash.flash_limit_bytes -ne $FlashLimit -or [int]$manifest.flash.baud -le 0 -or -not [bool]$manifest.flash.require_hash_verification) { throw 'Package manifest identity or safety metadata does not match the selected CI item.' }
    $offsets = @{}; $plan = @()
    foreach ($file in @($manifest.files)) {
        $path = [string]$file.archive_path; $size = [int64]$file.size
        if (-not (Test-RelativePackagePath $PackageDir $path) -or $path -notmatch '^bin/' -or [string]$file.sha256 -notmatch '^[0-9a-fA-F]{64}$' -or $size -le 0) { throw "Manifest file metadata is unsafe: $path" }
        $fullPath = Join-Path $PackageDir $path
        if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf) -or (Get-Item -LiteralPath $fullPath).Length -ne $size -or (Get-FileSha256 $fullPath) -ne [string]$file.sha256) { throw "Manifest file size or checksum verification failed: $path" }
        if ([string]$file.offset -notmatch '^0x[0-9a-fA-F]+$') { throw "Manifest flash offset is invalid: $path" }
        $offset = [Convert]::ToInt64(([string]$file.offset).Substring(2), 16)
        if ($offsets.ContainsKey($offset) -or $offset + $size -gt $FlashLimit) { throw "Manifest flash range is unsafe: $path" }
        $offsets[$offset] = $true; $plan += [pscustomobject]@{ Offset = $offset; Size = $size; Path = $fullPath }
    }
    if ($plan.Count -lt 1) { throw 'Package manifest contains no flashable files.' }
    $ordered = @($plan | Sort-Object Offset)
    for ($i = 1; $i -lt $ordered.Count; ++$i) { if ($ordered[$i - 1].Offset + $ordered[$i - 1].Size -gt $ordered[$i].Offset) { throw 'Package manifest contains overlapping flash ranges.' } }
    $flashArguments = Test-ManifestFlashArguments $manifest.flash
    return [pscustomobject]@{ Plan = $ordered; ManifestBaud = [int]$manifest.flash.baud; Before = $flashArguments.Before; After = $flashArguments.After; Stub = $flashArguments.Stub; WriteFlashArgs = $flashArguments.WriteFlashArgs }
}
function Invoke-CurrentFlash($Item, [string]$GhExe, [string]$PythonExe, [string]$Run, [string]$FinalSha) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'; $downloadDir = Join-Path $StateRoot (Join-Path 'downloads' $stamp)
    New-Item -ItemType Directory -Path $downloadDir -Force | Out-Null
    & $GhExe run download $Run --repo $Repo --name $Item.Artifact --dir $downloadDir
    if ($LASTEXITCODE -ne 0) { throw "Artifact download failed for exact artifact $($Item.Artifact)." }
    $zips = @(Get-ChildItem -LiteralPath $downloadDir -Recurse -File -Filter '*.zip')
    if ($zips.Count -ne 1) { throw 'Expected exactly one ZIP in the exact artifact download.' }
    $packageDir = Join-Path $downloadDir 'package'; Expand-Archive -LiteralPath $zips[0].FullName -DestinationPath $packageDir -ErrorAction Stop
    $checked = Test-PackageManifest $packageDir $Item $FinalSha
    $effectiveBaud = if ($Baud -gt 0) { $Baud } else { $checked.ManifestBaud }
    $arguments = @('-m', 'esptool', '--chip', $Chip, '--port', $Port, '--baud', $effectiveBaud, '--before', $checked.Before, '--after', $checked.After)
    if (-not $checked.Stub) { $arguments += '--no-stub' }
    $arguments += 'write_flash'; $arguments += $checked.WriteFlashArgs
    foreach ($entry in $checked.Plan) { $arguments += ('0x{0:X}' -f $entry.Offset); $arguments += $entry.Path }
    $output = (& $PythonExe @arguments 2>&1 | Out-String); $exitCode = $LASTEXITCODE
    return [pscustomobject]@{ Success = (($exitCode -eq 0) -and $output.Contains('Hash of data verified')); Output = $output }
}

$GitExe = Resolve-Git; $FinalSha = Resolve-FinalSha $GitExe; $Branch = Assert-CleanBranch $GitExe
$state = Read-State $FinalSha
if (Test-CompletedState $state) { Write-Output "All $($Items.Count) CI firmware items are already confirmed for $FinalSha."; return }
$GhExe = Resolve-Gh; Assert-ReadyPullRequest $GhExe $Branch $FinalSha; $PythonExe = Resolve-PythonWithEsptool; $Run = Resolve-ArtifactRun $GhExe $FinalSha
while ($true) {
    $item = $Items[$state.CurrentIndex - 1]
    Write-Output "Current $($item.Index)/$($Items.Count): $($item.Artifact)"
    $result = Invoke-CurrentFlash $item $GhExe $PythonExe $Run $FinalSha
    Write-Output $result.Output
    if (-not $result.Success) { throw 'Flash was not accepted: esptool must exit 0 and report Hash of data verified.' }
    if ((Read-Host 'After manual hardware verification, type PASS to advance') -cne 'PASS') { Write-Output 'Not advanced; manual PASS was not provided.'; return }
    $state = Get-NextProgress $state.CurrentIndex $state.ConfirmedIndexes $Items.Count
    Save-State $state.CurrentIndex $state.ConfirmedIndexes $FinalSha
    if ($state.Completed) { Write-Output "All $($Items.Count) CI firmware items passed manual verification."; return }
}
