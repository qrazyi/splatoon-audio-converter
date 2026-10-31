param([string]$Output="dist",[switch]$SkipBuild)
$ErrorActionPreference='Stop'
if(!$SkipBuild){& (Join-Path $PSScriptRoot 'build.ps1') -Output $Output}
$repository=Split-Path -Parent $PSScriptRoot
$distribution=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot $Output))
$application=Join-Path $distribution 'Splatoon Audio Converter'
$testFolder=Join-Path $PSScriptRoot 'test-output'
New-Item -ItemType Directory -Path $testFolder -Force | Out-Null
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$test=Join-Path $testFolder 'AudioConverter.Tests.exe'
$arguments=@('/nologo','/target:exe','/platform:x64','/optimize+','/debug-','/utf8output',"/out:$test",'/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.Core.dll',("/reference:{0}" -f (Join-Path $application 'Splatoon Audio Converter.exe')),("/reference:{0}" -f (Join-Path $repository 'src\splatoon_audio_converter\native\VGAudio.dll')),(Join-Path $PSScriptRoot 'tests\AudioTests.cs'))
& $compiler @arguments
if($LASTEXITCODE -ne 0){throw 'Test compilation failed.'}
Copy-Item -LiteralPath (Join-Path $application 'Splatoon Audio Converter.exe') -Destination $testFolder -Force
$testRuntime=Join-Path $testFolder '_internal'
New-Item -ItemType Directory -Path $testRuntime -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $application '_internal\zstd.dll') -Destination $testRuntime -Force
& $test (Join-Path $testFolder 'fixtures')
if($LASTEXITCODE -ne 0){throw 'Audio/interface tests failed.'}
