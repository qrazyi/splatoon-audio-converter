using System;
using System.IO;
using VGAudio.Containers.NintendoWare;
using VGAudio.Containers.Wave;

public static class NintendoAudioDecode
{
    public static int Main(string[] args)
    {
        try
        {
            if (args.Length != 2) throw new ArgumentException("Expected input and output paths");
            var audio = new BCFstmReader().Read(File.ReadAllBytes(args[0]));
            using (var stream = File.Create(args[1]))
                new WaveWriter().WriteToStream(audio, stream);
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error.Message);
            return 1;
        }
    }
}
