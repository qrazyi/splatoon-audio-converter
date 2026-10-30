using System;
using System.IO;
using VGAudio.Containers;
using VGAudio.Containers.NintendoWare;
using VGAudio.Containers.Wave;
using VGAudio.Formats;

public static class NintendoStreamEncode
{
    public static int Main(string[] args)
    {
        try
        {
            if (args.Length != 3)
                throw new ArgumentException("Expected original BFSTM, replacement WAV, and output BFSTM paths");

            AudioWithConfig original;
            AudioWithConfig replacement;
            using (var source = File.OpenRead(args[0]))
                original = new BCFstmReader().ReadWithConfig(source);
            using (var wav = File.OpenRead(args[1]))
                replacement = new WaveReader().ReadWithConfig(wav);

            if (replacement.AudioFormat.SampleRate != original.AudioFormat.SampleRate ||
                replacement.AudioFormat.ChannelCount != original.AudioFormat.ChannelCount)
                throw new ArgumentException("Replacement WAV sample rate and channels must match the original");

            int samples = replacement.AudioFormat.SampleCount;
            IAudioFormat format;
            if (original.AudioFormat.Looping)
            {
                int loopStart = (int)Math.Round(
                    (double)original.AudioFormat.LoopStart * samples / original.AudioFormat.SampleCount);
                loopStart = Math.Max(0, Math.Min(loopStart, samples - 1));
                format = replacement.AudioFormat.WithLoop(true, loopStart, samples);
            }
            else
            {
                format = replacement.AudioFormat.WithLoop(false);
            }

            var config = original.Configuration as BxstmConfiguration;
            if (config == null) throw new InvalidDataException("Original BFSTM has no stream configuration");
            config.RecalculateSeekTable = true;
            config.RecalculateLoopContext = true;
            config.LoopPointAlignment = 1;
            var result = new BCFstmWriter(NwTarget.Cafe).GetFile(new AudioData(format), config);
            File.WriteAllBytes(args[2], result);
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error.Message);
            return 1;
        }
    }
}
