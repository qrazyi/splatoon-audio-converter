using System;
using System.IO;
using VGAudio.Containers.Wave;
using VGAudio.Formats.GcAdpcm;

public static class GcAdpcmEncode
{
    public static int Main(string[] args)
    {
        try
        {
            if (args.Length != 2) throw new ArgumentException("Expected input WAV and output GCAE paths");
            var audio = new WaveReader().Read(File.ReadAllBytes(args[0]));
            var format = audio.GetFormat<GcAdpcmFormat>(null);
            using (var writer = new BinaryWriter(File.Create(args[1])))
            {
                writer.Write(new byte[] { 71, 67, 65, 69 });
                writer.Write(1);
                writer.Write(format.SampleRate);
                writer.Write(format.ChannelCount);
                writer.Write(format.SampleCount);
                foreach (var channel in format.Channels)
                {
                    writer.Write(channel.Gain);
                    foreach (short coefficient in channel.Coefs) writer.Write(coefficient);
                    channel.StartContext.Write(writer);
                    channel.LoopContext.Write(writer);
                    var encoded = channel.GetAdpcmAudio();
                    var decoded = channel.GetPcmAudio();
                    writer.Write(encoded.Length);
                    writer.Write(decoded.Length);
                    writer.Write(encoded);
                    foreach (short sample in decoded) writer.Write(sample);
                }
            }
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error.Message);
            return 1;
        }
    }
}
