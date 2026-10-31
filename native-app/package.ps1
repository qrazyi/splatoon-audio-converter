param([string]$Output="dist")
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$repository=Split-Path -Parent $PSScriptRoot
$distribution=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot $Output))
$application=Join-Path $distribution 'Splatoon Audio Converter'
$expected=@('Splatoon Audio Converter.exe','_internal/zstd.dll','_internal/licenses/Application-MIT.txt','_internal/licenses/VGAudio-MIT.txt','_internal/licenses/Zstandard-BSD.txt','_internal/licenses/NOTICES.txt')
$files=@(Get-ChildItem -LiteralPath $application -Recurse -File)
$relative=@($files | ForEach-Object {$_.FullName.Substring($application.Length+1).Replace('\','/')})
if(@(Compare-Object $expected $relative).Count -ne 0){throw 'Unexpected or missing files in portable app. Package only the approved EXE, native codec and notices.'}
if(($files | Measure-Object Length -Sum).Sum -ge 20MB){throw 'Portable folder exceeds 20 MiB.'}
function Assert-PrivatePathFree([string]$Path){
    $bytes=[IO.File]::ReadAllBytes($Path)
    $values=@([Text.Encoding]::UTF8.GetString($bytes),[Text.Encoding]::Unicode.GetString($bytes),[Text.Encoding]::Unicode.GetString($bytes,1,[Math]::Max(0,$bytes.Length-1)))
    foreach($value in $values){$normalized=$value.Replace('\','/') -replace '/+','/';if($normalized -match '(?i)(?:[a-z]:/users/|/(?:users|home)/)[^/\s\x00"'']{2,}') {throw "User-profile path detected in $([IO.Path]::GetFileName($Path))."}}
}
function Write-CleanZip([string]$Target,[object[]]$Entries){
    $stream=[IO.File]::Open($Target,[IO.FileMode]::Create)
    try{$zip=[IO.Compression.ZipArchive]::new($stream,[IO.Compression.ZipArchiveMode]::Create,$true)
        try{foreach($item in $Entries){Assert-PrivatePathFree $item.Path;$entry=$zip.CreateEntry(('Splatoon Audio Converter/'+$item.Name),[IO.Compression.CompressionLevel]::Optimal);$entry.LastWriteTime=[DateTimeOffset]::new(2000,1,1,0,0,0,[TimeSpan]::Zero);$dest=$entry.Open();try{$source=[IO.File]::OpenRead($item.Path);try{$source.CopyTo($dest)}finally{$source.Dispose()}}finally{$dest.Dispose()}}}finally{$zip.Dispose()}
    }finally{$stream.Dispose()}
    if((Get-Item -LiteralPath $Target).Length -ge 20MB){throw 'ZIP exceeds 20 MiB.'}
}
$portable=Join-Path $distribution 'Splatoon-Audio-Converter-win-x64.zip'
$entries=@($files | ForEach-Object { @{Path=$_.FullName;Name=$_.FullName.Substring($application.Length+1).Replace('\','/')} })
Write-CleanZip $portable $entries
$names=@('README.md','CHANGELOG.md','LICENSE','licenses/VGAudio-MIT.txt','fonts/README.md','docs/preview.png','docs/legacy.png','src/splatoon_audio_converter/native/VGAudio.dll','src/splatoon_audio_converter/assets/fonts/NinDev-Treasure_00.ttf','.github/workflows/build.yml')
$names+=@(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'src'),(Join-Path $PSScriptRoot 'tests'),(Join-Path $PSScriptRoot 'licenses'),(Join-Path $PSScriptRoot 'vendor') -Recurse -File | ForEach-Object {$_.FullName.Substring($repository.Length+1).Replace('\','/')})
$names+=@('native-app/build.ps1','native-app/build-codec.ps1','native-app/test.ps1','native-app/package.ps1','native-app/smoke.ps1','native-app/app.manifest')
$source=Join-Path $distribution 'Splatoon-Audio-Converter-source.zip'
Write-CleanZip $source @($names | Sort-Object -Unique | ForEach-Object {@{Path=(Join-Path $repository $_);Name=$_}})
$checksums=foreach($path in @($portable,$source)){('{0}  {1}' -f (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant(),[IO.Path]::GetFileName($path))}
[IO.File]::WriteAllText((Join-Path $distribution 'SHA256SUMS.txt'),(($checksums -join "`n")+"`n"),[Text.Encoding]::ASCII)
foreach($path in @($portable,$source)){Write-Output ('{0}: {1:N2} MiB ({2} bytes)' -f [IO.Path]::GetFileName($path),((Get-Item -LiteralPath $path).Length/1MB),(Get-Item -LiteralPath $path).Length)}
Write-Output 'PASS: exact release allowlist, no profile paths, no logs/settings/game audio, below 20 MiB.'
