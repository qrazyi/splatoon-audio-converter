# Optional dependency rebuild; ordinary app builds use the included codec DLL.
param()
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$work=Join-Path $PSScriptRoot 'build\zstd-static'
New-Item -ItemType Directory -Path $work -Force | Out-Null
$archive=Join-Path $work 'zstd-v1.5.7.zip'
$expected='7897bc5d620580d9b7cd3539c44b59d78f3657d33663fe97a145e07b4ebd69a4'
if(!(Test-Path -LiteralPath $archive)){Invoke-WebRequest -UseBasicParsing -Uri 'https://codeload.github.com/facebook/zstd/zip/refs/tags/v1.5.7' -OutFile $archive}
if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected){throw 'Official Zstandard source checksum mismatch.'}
$source=Join-Path $work 'zstd-1.5.7'
if(!(Test-Path -LiteralPath $source)){[IO.Compression.ZipFile]::ExtractToDirectory($archive,$work)}
$build=Join-Path $work 'compiled'
& cmake -S (Join-Path $source 'build\cmake') -B $build -A x64 -DZSTD_BUILD_SHARED=ON -DZSTD_BUILD_STATIC=OFF -DZSTD_BUILD_PROGRAMS=OFF -DZSTD_BUILD_TESTS=OFF -DZSTD_MULTITHREAD_SUPPORT=OFF -DZSTD_LEGACY_SUPPORT=OFF -DZSTD_USE_STATIC_RUNTIME=ON -DCMAKE_SHARED_LINKER_FLAGS=/DEBUG:NONE
if($LASTEXITCODE -ne 0){throw 'Codec configuration failed. Install CMake and the Visual Studio C++ build tools.'}
& cmake --build $build --config MinSizeRel --target libzstd_shared --parallel
if($LASTEXITCODE -ne 0){throw 'Codec build failed.'}
$library=@(Get-ChildItem -LiteralPath $build -Recurse -File -Filter 'libzstd.dll' | Where-Object {$_.Directory.Name -eq 'MinSizeRel'})
if($library.Count -ne 1){throw 'Expected exactly one release codec DLL.'}
Copy-Item -LiteralPath $library[0].FullName -Destination (Join-Path $PSScriptRoot 'vendor\zstd.dll') -Force
Write-Output 'Built codec with static C runtime: no separate Visual C++ redistributable needed.'
