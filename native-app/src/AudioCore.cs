using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using VGAudio.Containers.NintendoWare;
using VGAudio.Formats;
using VGAudio.Formats.GcAdpcm;
using VGAudio.Formats.Pcm16;

namespace SplatoonAudio {
    internal static class Binary {
        internal static void Check(byte[] b,int p,int n){if(p<0||n<0||p>b.Length-n)throw new InvalidDataException("The audio file is truncated or has invalid offsets.");}
        internal static ushort U16(byte[] b,int p,bool be=false){Check(b,p,2);return be?(ushort)(b[p]*256+b[p+1]):BitConverter.ToUInt16(b,p);}
        internal static uint U32(byte[] b,int p,bool be=false){Check(b,p,4);return be?((uint)b[p]<<24)|((uint)b[p+1]<<16)|((uint)b[p+2]<<8)|b[p+3]:BitConverter.ToUInt32(b,p);}
        internal static int I32(byte[] b,int p,bool be=false){return unchecked((int)U32(b,p,be));}
        internal static void Put(byte[] b,int p,uint value){Check(b,p,4);Buffer.BlockCopy(BitConverter.GetBytes(value),0,b,p,4);}
        internal static byte[] Slice(byte[] b,int p,int n){Check(b,p,n);var result=new byte[n];Buffer.BlockCopy(b,p,result,0,n);return result;}
        internal static string Magic(byte[] b,int p=0){Check(b,p,4);return Encoding.ASCII.GetString(b,p,4);}
        internal static string Text(byte[] b,int p){Check(b,p,1);int end=Array.IndexOf(b,(byte)0,p);if(end<0)throw new InvalidDataException("An audio name is not terminated.");return Encoding.UTF8.GetString(b,p,end-p);}
        internal static int Align(int n,int size){return checked((n+size-1)/size*size);}
        internal static short Clamp(double n){return (short)Math.Max(short.MinValue,Math.Min(short.MaxValue,Math.Round(n)));}
        internal static byte[] ReadFile(string path){var file=new FileInfo(path);if(file.Length>512L*1024*1024)throw new InvalidDataException("Audio files larger than 512 MB are not supported.");return File.ReadAllBytes(path);}
    }

    internal static class Zstd {
        const int Limit=512*1024*1024;
        [DllImport("zstd.dll",CallingConvention=CallingConvention.Cdecl)] static extern ulong ZSTD_getFrameContentSize(byte[] src,UIntPtr size);
        [DllImport("zstd.dll",CallingConvention=CallingConvention.Cdecl)] static extern UIntPtr ZSTD_decompress(byte[] dst,UIntPtr capacity,byte[] src,UIntPtr size);
        [DllImport("zstd.dll",CallingConvention=CallingConvention.Cdecl)] static extern UIntPtr ZSTD_compressBound(UIntPtr size);
        [DllImport("zstd.dll",CallingConvention=CallingConvention.Cdecl)] static extern UIntPtr ZSTD_compress(byte[] dst,UIntPtr capacity,byte[] src,UIntPtr size,int level);
        [DllImport("zstd.dll",CallingConvention=CallingConvention.Cdecl)] static extern uint ZSTD_isError(UIntPtr result);
        static int Result(UIntPtr result){if(ZSTD_isError(result)!=0)throw new InvalidDataException("Zstandard compression/decompression failed.");return checked((int)result.ToUInt64());}
        internal static byte[] Decompress(byte[] src){ulong size=ZSTD_getFrameContentSize(src,(UIntPtr)(uint)src.Length);if(size>Limit||size<4)throw new InvalidDataException("Invalid compressed audio size (maximum 512 MB).");var dst=new byte[(int)size];int actual=Result(ZSTD_decompress(dst,(UIntPtr)size,src,(UIntPtr)(uint)src.Length));if(actual!=dst.Length)throw new InvalidDataException("Compressed audio size mismatch.");return dst;}
        internal static byte[] Compress(byte[] src){int cap=checked((int)ZSTD_compressBound((UIntPtr)(uint)src.Length).ToUInt64());var dst=new byte[cap];int n=Result(ZSTD_compress(dst,(UIntPtr)(uint)cap,src,(UIntPtr)(uint)src.Length,3));return Binary.Slice(dst,0,n);}
    }

    internal sealed class PcmAudio {
        internal readonly int Rate;
        internal readonly short[][] Channels;
        internal int Frames {get{return Channels[0].Length;}}
        internal double Duration {get{return (double)Frames/Rate;}}
        internal PcmAudio(int rate,short[][] channels){if(rate<1||rate>384000||channels.Length<1||channels.Length>32||channels.Any(c=>c==null||c.Length!=channels[0].Length))throw new InvalidDataException("Invalid audio sample format.");Rate=rate;Channels=channels;}
        internal float[] Peaks(int bins=1200){if(Frames==0)return new float[0];bins=Math.Min(bins,Frames);var peaks=new float[bins];for(int i=0;i<Frames;i++){int slot=(int)((long)i*bins/Frames);int value=Math.Abs((int)Channels[0][i]);if(Channels.Length>1)value=Math.Max(value,Math.Abs((int)Channels[1][i]));peaks[slot]=Math.Max(peaks[slot],value/32768f);}return peaks;}
        internal static PcmAudio ReadWave(string path){return ReadWave(Binary.ReadFile(path));}
        internal static PcmAudio ReadWave(byte[] b){
            if(b.Length<12||Binary.Magic(b)!="RIFF"||Binary.Magic(b,8)!="WAVE")throw new InvalidDataException("Choose an uncompressed 16-bit PCM WAV file.");
            int channels=0,rate=0,bits=0,format=0,start=-1,length=0,block=0;
            for(int p=12;p<=b.Length-8;){int count=checked((int)Binary.U32(b,p+4));Binary.Check(b,p+8,count);string tag=Binary.Magic(b,p);
                if(tag=="fmt "){if(count<16)throw new InvalidDataException("Invalid WAV format chunk.");format=Binary.U16(b,p+8);channels=Binary.U16(b,p+10);rate=Binary.I32(b,p+12);block=Binary.U16(b,p+20);bits=Binary.U16(b,p+22);if(format==65534&&count>=40&&Binary.U16(b,p+24)>=22&&Binary.U16(b,p+26)==16&&Binary.Slice(b,p+32,16).SequenceEqual(new byte[]{1,0,0,0,0,0,16,0,128,0,0,170,0,56,155,113}))format=1;}
                else if(tag=="data"){start=p+8;length=count;}
                p=checked(p+8+count+(count&1));
            }
            if(format!=1||bits!=16||channels<1||channels>32||rate<1||rate>384000||block!=channels*2||start<0||length%block!=0)throw new InvalidDataException("Choose an uncompressed 16-bit PCM WAV file.");
            int frames=length/block;var output=new short[channels][];for(int c=0;c<channels;c++)output[c]=new short[frames];
            for(int i=0;i<frames;i++)for(int c=0;c<channels;c++)output[c][i]=(short)Binary.U16(b,start+(i*channels+c)*2);
            return new PcmAudio(rate,output);
        }
        internal byte[] WaveBytes(){using(var stream=new MemoryStream()){WriteWave(stream);return stream.ToArray();}}
        internal void WriteWave(string path){using(var stream=File.Create(path))WriteWave(stream);}
        internal void WriteWave(Stream stream){
            int size=checked(Frames*Channels.Length*2);var w=new BinaryWriter(stream,Encoding.UTF8,true);
            w.Write(Encoding.ASCII.GetBytes("RIFF"));w.Write(36+size);w.Write(Encoding.ASCII.GetBytes("WAVEfmt "));w.Write(16);w.Write((ushort)1);w.Write((ushort)Channels.Length);w.Write(Rate);w.Write(Rate*Channels.Length*2);w.Write((ushort)(Channels.Length*2));w.Write((ushort)16);w.Write(Encoding.ASCII.GetBytes("data"));w.Write(size);
            var buffer=new byte[Math.Min(8192,Math.Max(1,Frames))*Channels.Length*2];
            for(int start=0;start<Frames;){int n=Math.Min(buffer.Length/(Channels.Length*2),Frames-start);int p=0;for(int i=0;i<n;i++)for(int c=0;c<Channels.Length;c++){short sample=Channels[c][start+i];buffer[p++]=(byte)sample;buffer[p++]=(byte)(sample>>8);}stream.Write(buffer,0,p);start+=n;}w.Flush();
        }
        internal PcmAudio Match(int rate,int channels){
            if(channels<1||channels>2||Channels.Length>2)throw new InvalidDataException("Replacements must be mono or stereo; multichannel originals are preview/extract only.");
            if(Frames==0)throw new InvalidDataException("The replacement WAV has no samples.");
            var pcm=new short[channels][];
            for(int c=0;c<channels;c++){
                if(channels==Channels.Length)pcm[c]=Channels[c];
                else if(Channels.Length==1)pcm[c]=Channels[0];
                else{pcm[c]=new short[Frames];for(int i=0;i<Frames;i++)pcm[c][i]=Binary.Clamp((Channels[0][i]+(int)Channels[1][i])*.5);}
            }
            if(rate==Rate)return new PcmAudio(rate,pcm);
            int count=checked((int)Math.Round((double)Frames*rate/Rate));if(count<1)throw new InvalidDataException("The replacement is too short for the target sample rate.");
            double cutoff=Math.Min(1.0,(double)rate/Rate)*.96;int radius=Math.Min(96,(int)Math.Ceiling(24/cutoff)),taps=radius*2;const int phases=2048;
            var weights=new double[phases][];
            for(int phase=0;phase<phases;phase++){var row=new double[taps];double sum=0;for(int t=0;t<taps;t++){double d=t-radius+1-(double)phase/phases;double x=d*cutoff;double sinc=Math.Abs(x)<1e-12?1:Math.Sin(Math.PI*x)/(Math.PI*x);double window=Math.Abs(d)>=radius?0:.42+.5*Math.Cos(Math.PI*d/radius)+.08*Math.Cos(2*Math.PI*d/radius);row[t]=sinc*window*cutoff;sum+=row[t];}for(int t=0;t<taps;t++)row[t]/=sum;weights[phase]=row;}
            var resampled=new short[channels][];for(int c=0;c<channels;c++)resampled[c]=new short[count];
            for(int i=0;i<count;i++){double position=(double)i*Rate/rate;int center=(int)position;var row=weights[Math.Min(phases-1,(int)((position-center)*phases))];for(int c=0;c<channels;c++){double sum=0;for(int t=0;t<taps;t++)sum+=row[t]*pcm[c][Math.Max(0,Math.Min(Frames-1,center+t-radius+1))];resampled[c][i]=Binary.Clamp(sum);}}
            return new PcmAudio(rate,resampled);
        }
    }

    internal sealed class Track {
        internal int Index,Start,End,Rate,Frames,Channels,Codec,LoopStart,LoopEnd;
        internal string Name,Magic;internal bool Prefetch;
        internal double Duration {get{return (double)Frames/Rate;}}
        internal bool CanReplace {get{return !Prefetch&&Channels<=2&&(Magic=="BWAV"||Magic=="FSTM");}}
    }

    internal sealed class AudioDocument {
        internal readonly string Source;
        internal readonly byte[] Data;
        internal readonly bool Compressed;
        internal readonly string Kind;
        internal readonly List<Track> Tracks=new List<Track>();
        internal readonly Dictionary<int,PcmAudio> Replacements=new Dictionary<int,PcmAudio>();
        internal AudioDocument(string path):this(path,ReadArchive(Binary.ReadFile(path))){}
        internal AudioDocument(string path,byte[] data){
            Source=Path.GetFullPath(path);Compressed=path.EndsWith(".zs",StringComparison.OrdinalIgnoreCase);Data=data;Kind=Binary.Magic(data);
            if(Kind=="BWAV"||Kind=="FSTM"){Tracks.Add(Inspect(data,0,data.Length,0,BaseName(Path.GetFileName(path))));return;}
            if(Kind!="BARS"||data.Length<16)throw new InvalidDataException("Not a supported BARS, BWAV or BFSTM file.");
            int declared=checked((int)Binary.U32(data,4));if(declared<data.Length&&declared>=16&&data.Skip(declared).All(b=>b==0)){data=Binary.Slice(data,0,declared);Data=data;}
            if(declared!=data.Length)throw new InvalidDataException("The BARS size does not match its header.");
            int count=checked((int)Binary.U32(data,12));if(count<1||count>100000)throw new InvalidDataException("Invalid BARS sound count.");
            int table=checked(16+count*4);Binary.Check(data,table,checked(count*8));var offsets=new int[count];var meta=new int[count];
            for(int i=0;i<count;i++){meta[i]=checked((int)Binary.U32(data,table+i*8));offsets[i]=checked((int)Binary.U32(data,table+i*8+4));Binary.Check(data,offsets[i],4);}
            int[] sorted=offsets.Distinct().OrderBy(n=>n).ToArray();var names=new HashSet<string>(StringComparer.Ordinal);
            for(int i=0;i<count;i++){
                int m=meta[i];if(Binary.Magic(data,m)!="AMTA")throw new InvalidDataException("Invalid BARS metadata.");int nameAt;
                if(Binary.U16(data,m+6)==0x0400){int strg=checked(m+(int)Binary.U32(data,m+24));if(Binary.Magic(data,strg)!="STRG")throw new InvalidDataException("Invalid old BARS string block.");nameAt=strg+8;}
                else{nameAt=checked(m+36+(int)Binary.U32(data,m+36));}
                string name=Binary.Text(data,nameAt);if(!names.Add(name))throw new InvalidDataException("Duplicate sound names are not supported.");
                int order=Array.BinarySearch(sorted,offsets[i]);int end=order+1<sorted.Length?sorted[order+1]:data.Length;
                Tracks.Add(Inspect(data,offsets[i],end,i,name));
            }
        }
        internal static byte[] ReadArchive(byte[] data){if(data.Length<4)throw new InvalidDataException("The audio file is empty or truncated.");if(Binary.U32(data,0)==0xfd2fb528)data=Zstd.Decompress(data);string magic=Binary.Magic(data);if(magic!="BARS"&&magic!="BWAV"&&magic!="FSTM")throw new InvalidDataException("Open a .bars, .bwav or .bfstm file, optionally compressed as .zs.");return data;}
        internal static Track Inspect(byte[] b,int start,int end,int index,string name){
            Binary.Check(b,start,end-start);string magic=Binary.Magic(b,start);var t=new Track{Index=index,Name=name,Start=start,End=end,Magic=magic,LoopEnd=-1};
            if(magic=="BWAV"){
                Binary.Check(b,start,16);t.Channels=Binary.U16(b,start+14);if(t.Channels<1||t.Channels>32)throw new InvalidDataException("Unsupported BWAV channel count.");Binary.Check(b,start+16,t.Channels*76);
                t.Codec=Binary.U16(b,start+16);t.Rate=Binary.I32(b,start+20);t.Frames=Binary.I32(b,start+28);t.LoopEnd=Binary.I32(b,start+76);t.LoopStart=Binary.I32(b,start+80);
                t.Prefetch=Binary.U16(b,start+12)!=0||Binary.I32(b,start+24)>t.Frames;
                if(t.Codec>1)throw new InvalidDataException("This BWAV codec is not supported. PCM16 and DSP-ADPCM are supported.");
                for(int c=1;c<t.Channels;c++){int p=start+16+c*76;if(Binary.U16(b,p)!=t.Codec||Binary.I32(b,p+4)!=t.Rate||Binary.I32(b,p+12)!=t.Frames)throw new InvalidDataException("BWAV channel formats differ.");}
            }else if(magic=="FSTM"||magic=="FSTP"||magic=="FWAV"){
                Binary.Check(b,start,32);bool be=Binary.U16(b,start+4)==0xfffe;int info=checked(start+(int)Binary.U32(b,start+24,be));if(Binary.Magic(b,info)!="INFO")throw new InvalidDataException("Nintendo audio INFO block is missing.");int codec;
                if(magic=="FWAV"){codec=b[info+8];t.Rate=Binary.I32(b,info+12,be);t.LoopStart=Binary.I32(b,info+16,be);t.Frames=Binary.I32(b,info+20,be);t.Channels=Binary.I32(b,info+28,be);t.LoopEnd=b[info+9]!=0?t.Frames:-1;}
                else{int p=checked(info+8+(int)Binary.U32(b,info+12,be));Binary.Check(b,p,16);codec=b[p];t.Channels=b[p+2];t.Rate=Binary.I32(b,p+4,be);t.LoopStart=Binary.I32(b,p+8,be);t.Frames=Binary.I32(b,p+12,be);t.LoopEnd=b[p+1]!=0?t.Frames:-1;}
                t.Codec=-1-codec;t.Prefetch=magic=="FSTP";
            }else throw new InvalidDataException("Unsupported sound payload: "+magic);
            if(t.Rate<1||t.Rate>384000||t.Frames<1||t.Channels<1||t.Channels>32||t.LoopStart<0||(t.LoopEnd>=0&&((!t.Prefetch&&t.LoopEnd>t.Frames)||t.LoopStart>=t.LoopEnd)))throw new InvalidDataException("Invalid sound timing or channel metadata.");return t;
        }
        internal PcmAudio Decode(Track t){
            if(t.Magic=="BWAV"){
                var channels=new short[t.Channels][];int size=t.Codec==0?checked(t.Frames*2):checked((t.Frames+13)/14*8);
                for(int c=0;c<t.Channels;c++){int h=t.Start+16+c*76;int p=checked(t.Start+(int)Binary.U32(Data,h+52));Binary.Check(Data,p,size);if(p+size>t.End)throw new InvalidDataException("The sound payload is truncated.");
                    if(t.Codec==0){channels[c]=new short[t.Frames];Buffer.BlockCopy(Data,p,channels[c],0,size);}
                    else{var coefs=new short[16];for(int k=0;k<16;k++)coefs[k]=(short)Binary.U16(Data,h+16+k*2);channels[c]=DecodeDsp(Data,p,t.Frames,coefs,(short)Binary.U16(Data,h+70),(short)Binary.U16(Data,h+72));}
                }return new PcmAudio(t.Rate,channels);
            }
            byte[] bytes=Binary.Slice(Data,t.Start,t.End-t.Start);
            if(t.Magic=="FWAV")return DecodeFwav(bytes,t);
            var audio=new BCFstmReader().Read(bytes).GetFormat<Pcm16Format>(null);return new PcmAudio(audio.SampleRate,audio.Channels);
        }
        static short[] DecodeDsp(byte[] b,int p,int count,short[] coefficients,int h1,int h2){
            var result=new short[count];int n=0;
            while(n<count){byte head=b[p++];int predictor=head>>4,shift=head&15;if(predictor>7)throw new InvalidDataException("Invalid DSP-ADPCM predictor.");int c0=coefficients[predictor*2],c1=coefficients[predictor*2+1];
                for(int k=0;k<14&&n<count;k++){int nibble=(k&1)==0?b[p+k/2]>>4:b[p+k/2]&15;if(nibble>=8)nibble-=16;long sum=((long)nibble<<shift)*2048L+(long)c0*h1+(long)c1*h2+1024;int sample=(int)Math.Max(-32768,Math.Min(32767,sum>>11));result[n++]=(short)sample;h2=h1;h1=sample;}p+=7;
            }return result;
        }
        static PcmAudio DecodeFwav(byte[] b,Track t){
            bool be=Binary.U16(b,4)==0xfffe;int info=checked((int)Binary.U32(b,24,be));int data=checked((int)Binary.U32(b,36,be));if(Binary.Magic(b,data)!="DATA")throw new InvalidDataException("FWAV DATA block is missing.");int codec=b[info+8],table=info+28;var pcm=new short[t.Channels][];
            for(int c=0;c<t.Channels;c++){int channel=checked(table+(int)Binary.U32(b,table+8+c*8,be));int offset=checked(data+8+(int)Binary.U32(b,channel+4,be));pcm[c]=new short[t.Frames];
                if(codec==1){Binary.Check(b,offset,t.Frames*2);for(int i=0;i<t.Frames;i++)pcm[c][i]=(short)Binary.U16(b,offset+i*2,be);}
                else if(codec==0){Binary.Check(b,offset,t.Frames);for(int i=0;i<t.Frames;i++)pcm[c][i]=(short)((sbyte)b[offset+i]<<8);}
                else if(codec==2){int dsp=checked(channel+(int)Binary.U32(b,channel+12,be));var coefs=new short[16];for(int i=0;i<16;i++)coefs[i]=(short)Binary.U16(b,dsp+i*2,be);Binary.Check(b,offset,(t.Frames+13)/14*8);pcm[c]=DecodeDsp(b,offset,t.Frames,coefs,(short)Binary.U16(b,dsp+34,be),(short)Binary.U16(b,dsp+36,be));}
                else throw new InvalidDataException("Unsupported FWAV codec.");
            }return new PcmAudio(t.Rate,pcm);
        }
        internal static string BaseName(string name){bool changed;do{changed=false;foreach(string suffix in new[]{".bars.zs",".bwav.zs",".bfstm.zs",".bars",".bwav",".bfstm"})if(name.EndsWith(suffix,StringComparison.OrdinalIgnoreCase)){name=name.Substring(0,name.Length-suffix.Length);changed=true;break;}}while(changed);return string.IsNullOrWhiteSpace(name)?"audio":name;}
        internal string Extension {get{return Kind=="BARS"?".bars.zs":(Kind=="FSTM"?".bfstm":".bwav")+(Compressed?".zs":"");}}
        internal string NormalizeOutput(string path){return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(path)),BaseName(Path.GetFileName(path))+Extension);}
        internal bool ReadOnly {get{return Tracks.All(t=>!t.CanReplace);}}
        internal void SetReplacement(Track t,PcmAudio audio){if(!t.CanReplace)throw new InvalidDataException("This track is preview/extract only.");if(audio.Channels.Length>2||audio.Frames<1)throw new InvalidDataException("Choose a mono or stereo 16-bit PCM WAV with at least one sample.");Replacements[t.Index]=audio;}
        internal static string SafeName(string name){var invalid=Path.GetInvalidFileNameChars();return new string(name.Select(c=>invalid.Contains(c)||char.IsControl(c)?'_':c).ToArray()).Trim('.',' ');}
        internal void Extract(IEnumerable<Track> tracks,string folder){Directory.CreateDirectory(folder);foreach(var t in tracks){string name=SafeName(t.Name);if(string.IsNullOrWhiteSpace(name))name="sound";string path=Path.Combine(folder,t.Index.ToString("D3")+"_"+name+".wav");Decode(t).WriteWave(path);}}
        static uint Crc(byte[][] channels){uint crc=0xffffffff;foreach(var channel in channels)foreach(byte value in channel){crc^=value;for(int i=0;i<8;i++)crc=(crc>>1)^((crc&1)!=0?0xedb88320u:0);}return crc^0xffffffff;}
        static byte[] EncodeBwav(PcmAudio pcm,Track original){
            var audio=new AudioData(new Pcm16FormatBuilder(pcm.Channels,pcm.Rate).Build());var format=audio.GetFormat<GcAdpcmFormat>(null);var raw=format.Channels.Select(c=>c.GetAdpcmAudio()).ToArray();int frameSize=checked((pcm.Frames+13)/14*8);for(int i=0;i<raw.Length;i++)if(raw[i].Length!=frameSize)Array.Resize(ref raw[i],frameSize);
            int cursor=Binary.Align(16+raw.Length*76,64);var starts=new int[raw.Length];for(int i=0;i<raw.Length;i++){starts[i]=cursor;cursor=Binary.Align(checked(cursor+raw[i].Length),64);}var output=new byte[cursor];
            int loopStart=0,loopEnd=-1;if(original.LoopEnd>=0){loopStart=Math.Max(0,Math.Min(pcm.Frames-1,(int)Math.Round((double)original.LoopStart*pcm.Frames/original.Frames)));loopEnd=Math.Max(loopStart+1,Math.Min(pcm.Frames,(int)Math.Round((double)original.LoopEnd*pcm.Frames/original.Frames)));}
            using(var stream=new MemoryStream(output,true))using(var w=new BinaryWriter(stream)){w.Write(Encoding.ASCII.GetBytes("BWAV"));w.Write((ushort)0xfeff);w.Write((ushort)1);w.Write(Crc(raw));w.Write((ushort)0);w.Write((ushort)raw.Length);
                for(int c=0;c<raw.Length;c++){stream.Position=16+c*76;w.Write((ushort)1);w.Write((ushort)(raw.Length==1?2:c));w.Write(pcm.Rate);w.Write(pcm.Frames);w.Write(pcm.Frames);foreach(short coef in format.Channels[c].Coefs)w.Write(coef);w.Write(starts[c]);w.Write(starts[c]);w.Write(1);w.Write(loopEnd);w.Write(loopStart);format.Channels[c].StartContext.Write(w);stream.Position=starts[c];w.Write(raw[c]);}}
            return output;
        }
        internal byte[] Build(Action<string> progress){
            if(Replacements.Count==0)return Kind=="BARS"||Compressed?Zstd.Compress(Data):Data;
            if(ReadOnly)throw new InvalidDataException("This file contains tracks that are preview/extract only.");
            var replacements=new Dictionary<int,byte[]>();
            foreach(var pair in Replacements){var t=Tracks[pair.Key];if(!t.CanReplace)throw new InvalidDataException("This track is preview/extract only.");progress("Converting "+t.Name+"...");var pcm=pair.Value.Match(t.Rate,t.Channels);
                if(Kind=="FSTM"){
                    VGAudio.Containers.AudioWithConfig original;using(var stream=new MemoryStream(Data,false))original=new BCFstmReader().ReadWithConfig(stream);
                    IAudioFormat format=new Pcm16FormatBuilder(pcm.Channels,pcm.Rate).Build();if(t.LoopEnd>=0){int start=Math.Max(0,Math.Min(pcm.Frames-1,(int)Math.Round((double)t.LoopStart*pcm.Frames/t.Frames)));format=format.WithLoop(true,start,pcm.Frames);}else format=format.WithLoop(false);
                    var config=original.Configuration as BxstmConfiguration;if(config==null)throw new InvalidDataException("Missing BFSTM stream configuration.");config.RecalculateLoopContext=true;config.RecalculateSeekTable=true;config.LoopPointAlignment=1;
                    replacements[pair.Key]=new BCFstmWriter(NwTarget.Cafe).GetFile(new AudioData(format),config);
                }else replacements[pair.Key]=EncodeBwav(pcm,t);
                var info=Inspect(replacements[pair.Key],0,replacements[pair.Key].Length,0,t.Name);if(info.Rate!=t.Rate||info.Channels!=t.Channels||info.Frames!=pcm.Frames||(info.LoopEnd>=0)!=(t.LoopEnd>=0))throw new InvalidDataException("Converted audio failed validation.");
            }
            byte[] rebuilt;
            if(Kind!="BARS")rebuilt=replacements.ContainsKey(0)?replacements[0]:Data;
            else{int first=Tracks.Min(t=>t.Start),table=16+Tracks.Count*4;using(var stream=new MemoryStream()){stream.Write(Data,0,first);var starts=new int[Tracks.Count];foreach(var t in Tracks){while(stream.Length%64!=0)stream.WriteByte(0);starts[t.Index]=checked((int)stream.Length);byte[] b;if(!replacements.TryGetValue(t.Index,out b))b=Binary.Slice(Data,t.Start,t.End-t.Start);stream.Write(b,0,b.Length);}rebuilt=stream.ToArray();for(int i=0;i<starts.Length;i++)Binary.Put(rebuilt,table+i*8+4,(uint)starts[i]);Binary.Put(rebuilt,4,(uint)rebuilt.Length);}}
            var checkedFile=new AudioDocument(Source,rebuilt);if(!checkedFile.Tracks.Select(t=>t.Name).SequenceEqual(Tracks.Select(t=>t.Name)))throw new InvalidDataException("Saved sound names changed unexpectedly.");
            progress("Compressing and checking audio...");byte[] result=Kind=="BARS"||Compressed?Zstd.Compress(rebuilt):rebuilt;if(!ReadArchive(result).SequenceEqual(rebuilt))throw new InvalidDataException("Saved audio failed its compression check.");return result;
        }
        internal string Save(string chosenPath,Action<string> progress){
            string target=NormalizeOutput(chosenPath);if(string.Equals(Path.GetFullPath(target),Source,StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Choose a new filename. The original file is never overwritten.");byte[] bytes=Build(progress);Directory.CreateDirectory(Path.GetDirectoryName(target));string temp=target+"."+Guid.NewGuid().ToString("N")+".tmp";
            try{using(var stream=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None)){stream.Write(bytes,0,bytes.Length);stream.Flush(true);}if(File.Exists(target))File.Replace(temp,target,null);else File.Move(temp,target);}finally{if(File.Exists(temp))File.Delete(temp);}return target;
        }
    }
}
