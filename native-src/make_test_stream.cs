// Test fixture generator only. Not bundled in the desktop app.
using System;
using System.IO;
using VGAudio.Containers.NintendoWare;
using VGAudio.Containers.Wave;
using VGAudio.Formats;

public static class MakeTestStream
{
    public static void Main(string[] args)
    {
        using (var source = File.OpenRead(args[0]))
        {
            var original = new WaveReader().ReadWithConfig(source);
            var format = original.AudioFormat.WithLoop(true, 0, original.AudioFormat.SampleCount);
            File.WriteAllBytes(args[1], new BCFstmWriter(NwTarget.Cafe).GetFile(new AudioData(format)));
        }
    }
}
