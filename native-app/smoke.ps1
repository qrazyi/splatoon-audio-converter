param([string]$Output="dist")
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public static class SmokeAudioDevice { [DllImport("winmm.dll")] public static extern uint waveOutGetNumDevs(); }'
$distribution=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot $Output))
$zip=Join-Path $distribution 'Splatoon-Audio-Converter-win-x64.zip'
$tempBase=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$temporary=Join-Path $tempBase ('SplatoonAudioSmoke-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
$screenshots=Join-Path $PSScriptRoot 'test-output'
$fixtures=Join-Path $screenshots 'fixtures'
$environmentNames=@('PATH','PYTHONPATH','PYTHONHOME','QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH')
$original=@{}
foreach($name in $environmentNames){$original[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
try{
    [IO.Compression.ZipFile]::ExtractToDirectory($zip,$temporary)
    $exe=Join-Path $temporary 'Splatoon Audio Converter\Splatoon Audio Converter.exe'
    [Environment]::SetEnvironmentVariable('PATH',($env:WINDIR+'\System32;'+$env:WINDIR),'Process')
    foreach($name in $environmentNames | Where-Object {$_ -ne 'PATH'}){[Environment]::SetEnvironmentVariable($name,$null,'Process')}
    $cases=@(
        @('preview.bars','Legacy'),@('preview.bars.zs','Dorfic'),
        @('standalone.bwav','Aqua'),@('standalone.bwav.zs','Beige'),
        @('stream-2.bfstm','Dark Aero'),@('stream-2.bfstm.zs','Eco'),
        @('stream-10.bfstm','Legacy'),@('stream-10.bfstm.zs','Dorfic')
    )
    foreach($case in $cases){
        $sound=Join-Path $fixtures $case[0]
        if(!(Test-Path -LiteralPath $sound)){throw 'Run test.ps1 before smoke.ps1 to generate procedural fixtures.'}
        $image=Join-Path $screenshots ('native-'+$case[1].ToLowerInvariant().Replace(' ','-')+'-'+$case[0].Replace('.','-')+'.png')
        $start=[Diagnostics.ProcessStartInfo]::new();$start.FileName=$exe;$start.WorkingDirectory=$temporary;$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
        $start.Arguments='"'+$sound+'" --theme "'+$case[1]+'" --snapshot "'+$image+'"'
        if([SmokeAudioDevice]::waveOutGetNumDevs() -gt 0){$start.Arguments+=' --verify-playback'}
        $process=[Diagnostics.Process]::Start($start)
        try{if(!$process.WaitForExit(35000)){$process.Kill();throw 'Packaged app test timed out.'}if($process.ExitCode -ne 0){throw "Packaged app failed: $($case[0]) (exit $($process.ExitCode))."}}finally{$process.Dispose()}
        if(!(Test-Path -LiteralPath $image)){throw 'Packaged app did not render.'}
        Write-Output "PASS fresh ZIP: $($case[0]), $($case[1])"
    }
    $actual=@(Get-ChildItem -LiteralPath (Join-Path $temporary 'Splatoon Audio Converter') -Recurse -File)
    if($actual.Count -ne 6){throw 'App wrote an unexpected file beside the EXE.'}
    Write-Output 'PASS clean ZIP without Python/Qt/development paths. No personal files created beside app.'
}finally{
    foreach($name in $environmentNames){[Environment]::SetEnvironmentVariable($name,$original[$name],'Process')}
    $resolved=[IO.Path]::GetFullPath($temporary)
    if(!$resolved.StartsWith($tempBase,[StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($resolved) -notmatch '^SplatoonAudioSmoke-[a-f0-9]{32}$'){throw 'Refusing to clean an unexpected test path.'}
    if(Test-Path -LiteralPath $resolved){Remove-Item -LiteralPath $resolved -Recurse -Force}
}
