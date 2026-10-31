param([string]$Output="dist")
$ErrorActionPreference='Stop'
$project=$PSScriptRoot
$repository=Split-Path -Parent $project
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if(!(Test-Path -LiteralPath $compiler)){throw 'Install the Windows .NET Framework 4.8 developer tools to build.'}
$distribution=[IO.Path]::GetFullPath((Join-Path $project $Output))
$application=Join-Path $distribution 'Splatoon Audio Converter'
$runtime=Join-Path $application '_internal'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
$sources=Get-ChildItem -LiteralPath (Join-Path $project 'src') -Filter '*.cs' -File | Select-Object -ExpandProperty FullName
$library=Join-Path $repository 'src\splatoon_audio_converter\native\VGAudio.dll'
$font=Join-Path $repository 'src\splatoon_audio_converter\assets\fonts\NinDev-Treasure_00.ttf'
$executable=Join-Path $application 'Splatoon Audio Converter.exe'
$arguments=@('/nologo','/target:winexe','/platform:x64','/optimize+','/debug-','/utf8output',"/out:$executable",("/win32manifest:{0}" -f (Join-Path $project 'app.manifest')),'/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.Core.dll',"/reference:$library",("/resource:{0},SplatoonAudio.VGAudio.dll" -f $library),("/resource:{0},SplatoonAudio.Interface.ttf" -f $font))+$sources
& $compiler @arguments
if($LASTEXITCODE -ne 0){throw 'Application build failed.'}
Copy-Item -LiteralPath (Join-Path $project 'vendor\zstd.dll') -Destination (Join-Path $runtime 'zstd.dll') -Force
$licenses=Join-Path $runtime 'licenses'
New-Item -ItemType Directory -Path $licenses -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repository 'LICENSE') -Destination (Join-Path $licenses 'Application-MIT.txt') -Force
Copy-Item -LiteralPath (Join-Path $repository 'licenses\VGAudio-MIT.txt') -Destination $licenses -Force
Copy-Item -LiteralPath (Join-Path $project 'licenses\Zstandard-BSD.txt') -Destination $licenses -Force
Copy-Item -LiteralPath (Join-Path $project 'licenses\NOTICES.txt') -Destination $licenses -Force
$size=(Get-ChildItem -LiteralPath $application -Recurse -File | Measure-Object Length -Sum).Sum
if($size -ge 20MB){throw 'Portable app exceeds the 20 MiB size limit.'}
Write-Output ('Portable folder: {0:N2} MiB' -f ($size/1MB))
Write-Output "Built $executable"
