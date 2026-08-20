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
$SafeBefore = @('default_reset', 'no_reset', 'default-reset', 'no-reset')
$SafeAfter = @('hard_reset', 'no_reset', 'hard-reset', 'no-reset')
$BoardProfiles = @{
    rev1_3 = [pscustomobject]@{ Minimum = '1.0'; MaximumExclusive = '2.0' }
    rev3_x = [pscustomobject]@{ Minimum = '3.0'; MaximumExclusive = '4.0' }
}
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
        foreach ($profile in @('rev1_3', 'rev3_x')) {
            $Items += [pscustomobject]@{ Index = $index; Workflow = 'esp-idf-examples.yml'; Artifact = "firmware-esp-idf-$slug-$version-$profile"; Framework = 'esp-idf'; Version = $version; SourceProject = $project; Profile = $profile }
            $index++
        }
    }
}

function Test-Port([string]$Value) { return $Value -match '^COM\d+$' }
function Test-RevisionInRange([int]$Major, [int]$Minor, [string]$Minimum, [string]$MaximumExclusive) {
    $current = [version]"$Major.$Minor"
    return $current -ge [version]$Minimum -and $current -lt [version]$MaximumExclusive
}
function Get-ProfileForRevision([int]$Major, [int]$Minor) {
    foreach ($profile in @('rev1_3', 'rev3_x')) {
        $range = $BoardProfiles[$profile]
        if (Test-RevisionInRange $Major $Minor $range.Minimum $range.MaximumExclusive) { return $profile }
    }
    throw "Unsupported ESP32-P4 silicon revision v$Major.$Minor; supported ranges are [1.0, 2.0) and [3.0, 4.0)."
}
function Get-StatePath([string]$Root, [string]$Profile) {
    if (-not $BoardProfiles.ContainsKey($Profile)) { throw "Unsupported board profile: $Profile" }
    return Join-Path $Root "state-v3-$Profile.json"
}
function Assert-ProfileForRevision($Revision, $Item) {
    $expected = Get-ProfileForRevision $Revision.Major $Revision.Minor
    if ($expected -ne $Item.Profile) { throw "ESP32-P4 silicon revision v$($Revision.Major).$($Revision.Minor) requires $expected artifacts, not $($Item.Profile)." }
    if (-not $BoardProfiles.ContainsKey($Item.Profile) -or -not (Test-RevisionInRange $Revision.Major $Revision.Minor $BoardProfiles[$Item.Profile].Minimum $BoardProfiles[$Item.Profile].MaximumExclusive)) { throw "ESP32-P4 silicon revision v$($Revision.Major).$($Revision.Minor) is outside the supported $($Item.Profile) range." }
}
function ConvertFrom-EsptoolProbe([string]$Output) {
    if ($Output -notmatch '(?i)ESP32-P4') { throw 'Port probe did not identify ESP32-P4; unknown targets are rejected.' }
    $match = [regex]::Match($Output, '(?i)(?:revision|rev)\D*v?([0-9]+)\.([0-9]+)')
    if (-not $match.Success) { throw 'Port probe did not provide a parsable ESP32-P4 silicon revision; unknown targets are rejected.' }
    return [pscustomobject]@{ Major = [int]$match.Groups[1].Value; Minor = [int]$match.Groups[2].Value }
}
function Invoke-EsptoolProbe([string]$PythonExe, [string]$SelectedPort) {
    $output = (& $PythonExe -m esptool --chip $Chip --port $SelectedPort chip_id 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { $output = (& $PythonExe -m esptool --chip $Chip --port $SelectedPort chip-id 2>&1 | Out-String) }
    if ($LASTEXITCODE -ne 0) { throw 'ESP32-P4 read-only chip_id probe failed; no artifact will be downloaded or flashed.' }
    return ConvertFrom-EsptoolProbe $output
}
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
function New-ProgressState { return [pscustomobject]@{ CurrentIndex = $DefaultStartIndex; ConfirmedIndexes = @() } }
function Get-StateForArtifactRun($Saved, [string]$ExpectedSha, [string]$Profile, [string]$RunId, [int]$ItemCount = $Items.Count) {
    try {
        if (-not $Saved -or -not $Saved.PSObject.Properties['SchemaVersion'] -or [int]$Saved.SchemaVersion -ne 3 -or -not $Saved.PSObject.Properties['Profile'] -or [string]$Saved.Profile -ne $Profile -or -not $Saved.PSObject.Properties['FinalSha'] -or -not $Saved.PSObject.Properties['RunId'] -or -not $Saved.PSObject.Properties['CurrentIndex'] -or -not $Saved.PSObject.Properties['ConfirmedIndexes'] -or [string]$Saved.FinalSha -ne $ExpectedSha -or [string]$Saved.RunId -ne $RunId) {
            return New-ProgressState
        }
        $current = [int]$Saved.CurrentIndex
        if ($current -lt 1 -or $current -gt $ItemCount) { return New-ProgressState }
        $confirmed = @($Saved.ConfirmedIndexes | ForEach-Object { [int]$_ } | Where-Object { $_ -ge 1 -and $_ -le $ItemCount } | Sort-Object -Unique)
        $expected = if ($current -eq $ItemCount -and $confirmed -contains $ItemCount) { @(1..$ItemCount) } elseif ($current -eq 1) { @() } else { @(1..($current - 1)) }
        if (@($confirmed).Count -ne @($expected).Count -or @($confirmed | Where-Object { $_ -notin $expected }).Count -ne 0) { return New-ProgressState }
        return [pscustomobject]@{ CurrentIndex = $current; ConfirmedIndexes = $confirmed }
    } catch { return New-ProgressState }
}
function ConvertFrom-StateJson([string]$Raw) { try { if ([string]::IsNullOrWhiteSpace($Raw)) { return $null }; return $Raw | ConvertFrom-Json } catch { return $null } }
function Get-StateTempPath([string]$StateFile) { return Join-Path ([System.IO.Path]::GetDirectoryName($StateFile)) ('.{0}.{1}.tmp' -f [System.IO.Path]::GetFileName($StateFile), [guid]::NewGuid().ToString('N')) }
function Test-ArtifactInventory($Inventory) {
    try {
        $expected = @($Items | ForEach-Object { [string]$_.Artifact } | Sort-Object -Unique)
        if ($expected.Count -ne 48 -or -not $Inventory -or -not $Inventory.PSObject.Properties['TotalCount'] -or -not $Inventory.PSObject.Properties['Artifacts']) { return $false }
        $artifacts = @($Inventory.Artifacts)
        if ([int]$Inventory.TotalCount -ne $expected.Count -or $artifacts.Count -ne $expected.Count) { return $false }
        $names = @($artifacts | ForEach-Object { if (-not $_.PSObject.Properties['name'] -or -not $_.PSObject.Properties['expired'] -or $_.expired -ne $false) { throw 'Artifact inventory is incomplete or expired.' }; [string]$_.name })
        $unique = @($names | Sort-Object -Unique)
        return $unique.Count -eq $expected.Count -and @($expected | Where-Object { $_ -notin $unique }).Count -eq 0 -and @($unique | Where-Object { $_ -notin $expected }).Count -eq 0
    } catch { return $false }
}
function Test-CompletedState($State, [int]$ItemCount = $Items.Count) {
    return $State -and $State.CurrentIndex -eq $ItemCount -and @($State.ConfirmedIndexes | Sort-Object -Unique).Count -eq $ItemCount -and @($State.ConfirmedIndexes | Where-Object { $_ -notin @(1..$ItemCount) }).Count -eq 0
}
function Get-FileSha256([string]$Path) {
    $stream = $null; $algorithm = $null
    try { $stream = [System.IO.File]::OpenRead($Path); $algorithm = [System.Security.Cryptography.SHA256]::Create(); return [System.BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { if ($null -ne $stream) { $stream.Dispose() }; if ($null -ne $algorithm) { $algorithm.Dispose() } }
}

if ($SelfTest) {
    if ($Items.Count -ne 48) { throw 'SelfTest expected exactly 48 ESP-IDF items.' }
    if (@($Items | Where-Object { $_.Profile -notin @('rev1_3', 'rev3_x') -or $_.Artifact -notmatch '-(rev1_3|rev3_x)$' }).Count -ne 0) { throw 'SelfTest artifact profile inventory failed.' }
    $rev1 = ConvertFrom-EsptoolProbe "Chip is ESP32-P4; revision v1.0"
    $rev1Item = @($Items | Where-Object { $_.Profile -eq 'rev1_3' })[0]
    Assert-ProfileForRevision $rev1 $rev1Item
    if ((Get-ProfileForRevision $rev1.Major $rev1.Minor) -ne 'rev1_3') { throw 'SelfTest rev1.x profile mapping failed.' }
    $rev3Item = @($Items | Where-Object { $_.Profile -eq 'rev3_x' })[0]
    $rev3 = ConvertFrom-EsptoolProbe "ESP32-P4 rev 3.0"
    Assert-ProfileForRevision $rev3 $rev3Item
    if ((Get-ProfileForRevision $rev3.Major $rev3.Minor) -ne 'rev3_x') { throw 'SelfTest rev3_x profile mapping failed.' }
    foreach ($accepted in @(
        [pscustomobject]@{ Output = 'ESP32-P4 rev 1.3'; Profile = 'rev1_3' },
        [pscustomobject]@{ Output = 'ESP32-P4 revision v1.99'; Profile = 'rev1_3' },
        [pscustomobject]@{ Output = 'ESP32-P4 rev 3.99'; Profile = 'rev3_x' }
    )) {
        $probe = ConvertFrom-EsptoolProbe $accepted.Output
        if ((Get-ProfileForRevision $probe.Major $probe.Minor) -ne $accepted.Profile) { throw "SelfTest accepted revision mapping failed for $($accepted.Output)." }
    }
    foreach ($unsupported in @('ESP32-P4 rev 0.99', 'ESP32-P4 rev 2.0', 'ESP32-P4 rev 2.99', 'ESP32-P4 rev 4.0')) {
        $rejected = $false
        try {
            $probe = ConvertFrom-EsptoolProbe $unsupported
            $null = Get-ProfileForRevision $probe.Major $probe.Minor
        } catch {
            if ($_.Exception.Message -notmatch '^Unsupported ESP32-P4 silicon revision') { throw }
            $rejected = $true
        }
        if (-not $rejected) { throw "SelfTest unsupported revision was accepted: $unsupported" }
    }
    $manifestMismatch = $false
    $manifest = [pscustomobject]@{ board_profile = 'rev3_x'; chip_revision = [pscustomobject]@{ minimum = '3.0'; maximum_exclusive = '4.0' }; c6_firmware_included = $false }
    if ($manifest.board_profile -ne $rev1Item.Profile -or -not (Test-RevisionInRange $rev1.Major $rev1.Minor $manifest.chip_revision.minimum $manifest.chip_revision.maximum_exclusive)) { $manifestMismatch = $true }
    if (-not $manifestMismatch) { throw 'SelfTest manifest profile mismatch failed.' }
    $selfTestRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'waveshare-lcd5-selftest'
    $rev1State = Get-StatePath $selfTestRoot 'rev1_3'
    if ([System.IO.Path]::GetFileName($rev1State) -ne 'state-v3-rev1_3.json' -or $rev1State -eq (Join-Path $selfTestRoot 'state-v3-rev3_x.json')) { throw 'SelfTest profile state isolation failed.' }
    $profileItemCount = 24
    foreach ($selectedProfile in @('rev1_3', 'rev3_x')) {
        $profileItems = @($Items | Where-Object { $_.Profile -eq $selectedProfile })
        if ($profileItems.Count -ne $profileItemCount -or @($profileItems | Where-Object { $_.Profile -ne $selectedProfile }).Count -ne 0) { throw "SelfTest expected exactly $profileItemCount isolated items for $selectedProfile." }
        $current = 1; $confirmed = @(); $transitions = 0
        while ($current -lt $profileItems.Count) { $next = Get-NextProgress $current $confirmed $profileItems.Count; if ($next.Completed -or $next.CurrentIndex -ne ($current + 1)) { throw "SelfTest progress transition failed for $selectedProfile." }; $current = $next.CurrentIndex; $confirmed = @($next.ConfirmedIndexes); $transitions++ }
        $last = Get-NextProgress $current $confirmed $profileItems.Count
        if (-not $last.Completed -or @($last.ConfirmedIndexes).Count -ne $profileItemCount) { throw "SelfTest did not complete $selectedProfile." }
    }
    $reset = Get-StateForArtifactRun ([pscustomobject]@{ SchemaVersion = 3; Profile = 'rev1_3'; FinalSha = 'other'; RunId = '101'; CurrentIndex = 4; ConfirmedIndexes = @(1,2,3) }) ('a' * 40) 'rev1_3' '101'
    if ($reset.CurrentIndex -ne 1 -or @($reset.ConfirmedIndexes).Count -ne 0) { throw 'SelfTest SHA reset failed.' }
    $runReset = Get-StateForArtifactRun ([pscustomobject]@{ SchemaVersion = 3; Profile = 'rev1_3'; FinalSha = ('a' * 40); RunId = '101'; CurrentIndex = 4; ConfirmedIndexes = @(1,2,3) }) ('a' * 40) 'rev1_3' '102'
    if ($runReset.CurrentIndex -ne 1 -or @($runReset.ConfirmedIndexes).Count -ne 0) { throw 'SelfTest run reset failed.' }
    $complete = Get-StateForArtifactRun ([pscustomobject]@{ SchemaVersion = 3; Profile = 'rev1_3'; FinalSha = ('a' * 40); RunId = '101'; CurrentIndex = 24; ConfirmedIndexes = @(1..24) }) ('a' * 40) 'rev1_3' '101' $profileItemCount
    if (-not (Test-CompletedState $complete $profileItemCount)) { throw 'SelfTest completed-state recovery failed.' }
    if ($null -ne (ConvertFrom-StateJson '{')) { throw 'SelfTest malformed state reset failed.' }
    if ([System.IO.Path]::GetDirectoryName((Get-StateTempPath $rev1State)) -ne [System.IO.Path]::GetDirectoryName($rev1State)) { throw 'SelfTest atomic state temporary path failed.' }
    $fullInventory = [pscustomobject]@{ TotalCount = $Items.Count; Artifacts = @($Items | ForEach-Object { [pscustomobject]@{ name = $_.Artifact; expired = $false } }) }
    if (-not (Test-ArtifactInventory $fullInventory) -or (Test-ArtifactInventory ([pscustomobject]@{ TotalCount = ($Items.Count - 1); Artifacts = @($fullInventory.Artifacts | Select-Object -First ($Items.Count - 1)) }))) { throw 'SelfTest exact artifact inventory failed.' }
    $selfTestPackageRoot = Join-Path $selfTestRoot 'package'
    if ((Test-RelativePackagePath $selfTestPackageRoot ([System.IO.Path]::Combine('..', 'escape.bin'))) -or (Test-RelativePackagePath $selfTestPackageRoot (Join-Path $selfTestRoot 'escape.bin')) -or -not (Test-RelativePackagePath $selfTestPackageRoot ([System.IO.Path]::Combine('bin', 'app.bin')))) { throw 'SelfTest path boundary failed.' }
    Write-Output 'SELF_TEST_OK items=48 profile_items=24 profiles=rev1_3,rev3_x parser=ok rev1_x=allowed rev3_x=allowed unsupported_gaps=blocked manifest_mismatch=blocked state-v3=profile-isolated transitions=23 sha_reset=ok run_reset=ok malformed_state_reset=ok atomic_state_temp=ok artifact_inventory=48-exact-unexpired completed_recovery=ok path_boundary=ok'
    return
}
if ($ListOnly) {
    Write-Output 'finalSHA=resolved-at-runtime'
    Write-Output 'port=must-be-explicit-in-normal-mode'
    Write-Output "items=$($Items.Count)"
    foreach ($item in $Items) { Write-Output ('{0}: workflow={1} artifact={2} profile={3} source={4}' -f $item.Index, $item.Workflow, $item.Artifact, $item.Profile, $item.SourceProject) }
    return
}
if ([string]::IsNullOrWhiteSpace($Port)) { throw 'Port is required in normal mode; pass -Port COMx.' }
$Port = $Port.Trim().ToUpperInvariant()
if (-not (Test-Port $Port)) { throw 'Port must be COM followed by digits, for example COMx.' }
if ($Baud -lt 0) { throw 'Baud must be positive when supplied.' }

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$StateRoot = Join-Path $env:LOCALAPPDATA 'Waveshare\ESP32-P4-WIFI6-Touch-LCD-5\ci-firmware'
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
    foreach ($run in $runs) {
        $artifactRaw = (& $GhExe api --method GET "repos/$Repo/actions/runs/$($run.databaseId)/artifacts?per_page=100" 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) { throw "Unable to list artifacts for successful workflow run $($run.databaseId)." }
        try {
            $artifactPayload = $artifactRaw | ConvertFrom-Json
            $inventory = [pscustomobject]@{ TotalCount = $artifactPayload.total_count; Artifacts = @($artifactPayload.artifacts) }
        } catch { throw "Unable to parse artifacts for successful workflow run $($run.databaseId)." }
        if (Test-ArtifactInventory $inventory) { return [string]$run.databaseId }
    }
    throw 'No successful exact-SHA workflow run reports exactly the 48 expected unique, unexpired firmware artifacts; partial dispatch runs are rejected.'
}
function Read-State([string]$FinalSha, [string]$Profile, [string]$RunId, [int]$ItemCount) {
    $saved = $null
    if (Test-Path -LiteralPath $StatePath) {
        try { $saved = ConvertFrom-StateJson ([System.IO.File]::ReadAllText($StatePath)) } catch { return New-ProgressState }
    }
    return Get-StateForArtifactRun $saved $FinalSha $Profile $RunId $ItemCount
}
function Save-State([int]$CurrentIndex, [int[]]$ConfirmedIndexes, [string]$FinalSha, [string]$Profile, [string]$RunId) {
    $stateDirectory = [System.IO.Path]::GetDirectoryName($StatePath)
    if (-not (Test-Path -LiteralPath $stateDirectory)) { New-Item -ItemType Directory -Path $stateDirectory | Out-Null }
    $temporaryPath = Get-StateTempPath $StatePath
    try {
        $payload = [pscustomobject]@{ SchemaVersion = 3; Profile = $Profile; FinalSha = $FinalSha; RunId = $RunId; CurrentIndex = $CurrentIndex; ConfirmedIndexes = @($ConfirmedIndexes | Sort-Object -Unique); UpdatedAt = (Get-Date).ToString('o') } | ConvertTo-Json
        [System.IO.File]::WriteAllText($temporaryPath, $payload, [System.Text.UTF8Encoding]::new($false))
        if ([System.IO.File]::Exists($StatePath)) { [System.IO.File]::Replace($temporaryPath, $StatePath, $null) } else { [System.IO.File]::Move($temporaryPath, $StatePath) }
    } finally {
        if ([System.IO.File]::Exists($temporaryPath)) { Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue }
    }
}
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
    $range = $manifest.chip_revision
    if ($manifest.schema_version -ne 1 -or $manifest.board -ne $Board -or $manifest.chip -ne $Chip -or $manifest.board_profile -ne $Item.Profile -or -not $range -or [string]$range.minimum -ne $BoardProfiles[$Item.Profile].Minimum -or [string]$range.maximum_exclusive -ne $BoardProfiles[$Item.Profile].MaximumExclusive -or [bool]$manifest.c6_firmware_included -or $manifest.framework -ne $Item.Framework -or $manifest.framework_version -ne $Item.Version -or $manifest.source_project -ne $Item.SourceProject -or $manifest.git_sha -notmatch '^[0-9a-fA-F]{40}$' -or -not [string]::Equals([string]$manifest.git_sha, $FinalSha, [System.StringComparison]::OrdinalIgnoreCase) -or [int64]$manifest.flash.flash_limit_bytes -ne $FlashLimit -or [int]$manifest.flash.baud -le 0 -or -not [bool]$manifest.flash.require_hash_verification) { throw 'Package manifest identity, profile, revision range, or safety metadata does not match the selected CI item.' }
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
    $revision = Invoke-EsptoolProbe $PythonExe $Port
    Assert-ProfileForRevision $revision $Item
    Write-Warning 'Silicon revision does not replace PCB/electrical revision confirmation.'
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
$PythonExe = Resolve-PythonWithEsptool
$revision = Invoke-EsptoolProbe $PythonExe $Port
$DetectedProfile = Get-ProfileForRevision $revision.Major $revision.Minor
if (-not $BoardProfiles.ContainsKey($DetectedProfile)) { throw "Unsupported ESP32-P4 silicon revision profile: $DetectedProfile." }
Write-Warning 'Silicon revision does not replace PCB/electrical revision confirmation.'
$ProfileItems = @($Items | Where-Object { $_.Profile -eq $DetectedProfile })
if ($ProfileItems.Count -ne 24) { throw "Expected exactly 24 CI firmware items for $DetectedProfile." }
$StatePath = Get-StatePath $StateRoot $DetectedProfile
$GhExe = Resolve-Gh; Assert-ReadyPullRequest $GhExe $Branch $FinalSha; $Run = Resolve-ArtifactRun $GhExe $FinalSha
$state = Read-State $FinalSha $DetectedProfile $Run $ProfileItems.Count
if (Test-CompletedState $state $ProfileItems.Count) { Write-Output "All $($ProfileItems.Count) $DetectedProfile CI firmware items are already confirmed for $FinalSha from workflow run $Run."; return }
while ($true) {
    $item = $ProfileItems[$state.CurrentIndex - 1]
    Write-Output "Current $($state.CurrentIndex)/$($ProfileItems.Count): $($item.Artifact)"
    $result = Invoke-CurrentFlash $item $GhExe $PythonExe $Run $FinalSha
    Write-Output $result.Output
    if (-not $result.Success) { throw 'Flash was not accepted: esptool must exit 0 and report Hash of data verified.' }
    if ((Read-Host 'After manual hardware verification, type PASS to advance') -cne 'PASS') { Write-Output 'Not advanced; manual PASS was not provided.'; return }
    $state = Get-NextProgress $state.CurrentIndex $state.ConfirmedIndexes $ProfileItems.Count
    Save-State $state.CurrentIndex $state.ConfirmedIndexes $FinalSha $DetectedProfile $Run
    if ($state.Completed) { Write-Output "All $($ProfileItems.Count) $DetectedProfile CI firmware items passed manual verification."; return }
}
