using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace SplatoonAudio {
    internal interface IWaveDevice:IDisposable {
        int FreeSlots {get;}
        int Pending {get;}
        long Position {get;}
        void Queue(byte[] pcm);
        void Pause();void Resume();void Reset();
    }
    internal sealed class WinWaveDevice:IWaveDevice {
        [StructLayout(LayoutKind.Sequential,Pack=2)] struct Format {internal ushort Tag,Channels;internal uint Rate,ByteRate;internal ushort Align,Bits,Extra;}
        [StructLayout(LayoutKind.Sequential)] struct Header {internal IntPtr Data;internal uint Length,Recorded;internal UIntPtr User;internal uint Flags,Loops;internal IntPtr Next;internal UIntPtr Reserved;}
        [StructLayout(LayoutKind.Sequential)] struct Time {internal uint Type,Value,Padding;}
        [DllImport("winmm.dll")] static extern uint waveOutOpen(out IntPtr device,uint id,ref Format format,IntPtr callback,IntPtr instance,uint flags);
        [DllImport("winmm.dll")] static extern uint waveOutPrepareHeader(IntPtr device,IntPtr header,uint size);
        [DllImport("winmm.dll")] static extern uint waveOutUnprepareHeader(IntPtr device,IntPtr header,uint size);
        [DllImport("winmm.dll")] static extern uint waveOutWrite(IntPtr device,IntPtr header,uint size);
        [DllImport("winmm.dll")] static extern uint waveOutPause(IntPtr device);
        [DllImport("winmm.dll")] static extern uint waveOutRestart(IntPtr device);
        [DllImport("winmm.dll")] static extern uint waveOutReset(IntPtr device);
        [DllImport("winmm.dll")] static extern uint waveOutClose(IntPtr device);
        [DllImport("winmm.dll")] static extern uint waveOutGetPosition(IntPtr device,ref Time time,uint size);
        [DllImport("winmm.dll")] internal static extern uint waveOutGetNumDevs();
        [DllImport("winmm.dll",CharSet=CharSet.Unicode)] static extern uint waveOutGetErrorTextW(uint code,StringBuilder text,uint size);
        sealed class Slot {internal IntPtr Header,Data;internal bool Queued;}
        readonly List<Slot> slots=new List<Slot>();IntPtr handle;readonly int channels,rate;readonly uint headerSize=(uint)Marshal.SizeOf(typeof(Header));
        static void Check(uint code){if(code==0)return;var text=new StringBuilder(256);waveOutGetErrorTextW(code,text,256);throw new InvalidOperationException("Audio output: "+text.ToString());}
        internal WinWaveDevice(int rate,int channels){
            this.rate=rate;this.channels=channels;var format=new Format{Tag=1,Channels=(ushort)channels,Rate=(uint)rate,ByteRate=(uint)(rate*channels*2),Align=(ushort)(channels*2),Bits=16};
            Check(waveOutOpen(out handle,uint.MaxValue,ref format,IntPtr.Zero,IntPtr.Zero,0));
            try{for(int i=0;i<4;i++){var slot=new Slot{Data=Marshal.AllocHGlobal(2048*channels*2),Header=Marshal.AllocHGlobal((int)headerSize)};slots.Add(slot);Marshal.StructureToPtr(new Header{Data=slot.Data,Length=(uint)(2048*channels*2)},slot.Header,false);Check(waveOutPrepareHeader(handle,slot.Header,headerSize));}}catch{Dispose();throw;}
        }
        bool Free(Slot slot){return !slot.Queued||(((Header)Marshal.PtrToStructure(slot.Header,typeof(Header))).Flags&1)!=0;}
        public int FreeSlots {get{int n=0;foreach(var s in slots)if(Free(s))n++;return n;}}
        public int Pending {get{return slots.Count-FreeSlots;}}
        public long Position {get{var time=new Time{Type=2};if(waveOutGetPosition(handle,ref time,(uint)Marshal.SizeOf(typeof(Time)))!=0)return 0;return time.Type==2?time.Value:time.Type==4?time.Value/(channels*2L):(long)time.Value*rate/1000;}}
        public void Queue(byte[] bytes){foreach(var slot in slots)if(Free(slot)){if(bytes.Length>2048*channels*2)throw new ArgumentException("Audio buffer too large.");Marshal.Copy(bytes,0,slot.Data,bytes.Length);var h=(Header)Marshal.PtrToStructure(slot.Header,typeof(Header));h.Length=(uint)bytes.Length;h.Flags&=~1u;Marshal.StructureToPtr(h,slot.Header,false);Check(waveOutWrite(handle,slot.Header,headerSize));slot.Queued=true;return;}throw new InvalidOperationException("No free audio buffer.");}
        public void Pause(){Check(waveOutPause(handle));}public void Resume(){Check(waveOutRestart(handle));}
        public void Reset(){if(handle!=IntPtr.Zero){Check(waveOutReset(handle));foreach(var s in slots)s.Queued=false;}}
        public void Dispose(){if(handle==IntPtr.Zero)return;waveOutReset(handle);foreach(var slot in slots){waveOutUnprepareHeader(handle,slot.Header,headerSize);Marshal.FreeHGlobal(slot.Header);Marshal.FreeHGlobal(slot.Data);}slots.Clear();waveOutClose(handle);handle=IntPtr.Zero;}
    }

    internal sealed class SimulatedWaveDevice:IWaveDevice {
        readonly Stopwatch clock=new Stopwatch();readonly Queue<long> ends=new Queue<long>();readonly int rate,channels;long queued;
        internal SimulatedWaveDevice(int rate,int channels){this.rate=rate;this.channels=channels;clock.Start();}
        public long Position {get{return Math.Min(queued,(long)(clock.Elapsed.TotalSeconds*rate));}}
        public int Pending {get{while(ends.Count>0&&ends.Peek()<=Position)ends.Dequeue();return ends.Count;}}
        public int FreeSlots {get{return 4-Pending;}}
        public void Queue(byte[] pcm){queued+=pcm.Length/(channels*2);ends.Enqueue(queued);}
        public void Pause(){clock.Stop();}public void Resume(){clock.Start();}public void Reset(){ends.Clear();queued=0;clock.Reset();clock.Start();}public void Dispose(){clock.Stop();}
    }

    internal sealed class WavePlayer:IDisposable {
        sealed class Request {internal string Name;internal PcmAudio Audio;internal int Frame;}
        readonly ConcurrentQueue<Request> commands=new ConcurrentQueue<Request>();readonly AutoResetEvent wake=new AutoResetEvent(false);readonly Thread worker;readonly bool simulated;
        IWaveDevice device;PcmAudio source;int readFrame,baseFrame,state;long position,bytes;float volume=1;double gain=1;bool closing,disposed;string error;
        internal WavePlayer(bool simulated=false){this.simulated=simulated;worker=new Thread(Run){IsBackground=true,Name="Audio playback",Priority=ThreadPriority.AboveNormal};worker.Start();}
        internal int State {get{return Volatile.Read(ref state);}} // 0 stopped, 1 playing, 2 paused
        internal long PositionFrames {get{return Interlocked.Read(ref position);}}
        internal long BytesWritten {get{return Interlocked.Read(ref bytes);}}
        internal string Error {get{return Volatile.Read(ref error);}}
        internal float Volume {get{return Volatile.Read(ref volume);}set{Volatile.Write(ref volume,Math.Max(0,Math.Min(3,value)));}}
        void Send(string name,PcmAudio audio=null,int frame=0){if(disposed)return;commands.Enqueue(new Request{Name=name,Audio=audio,Frame=frame});wake.Set();}
        internal void SetSource(PcmAudio audio){Send("source",audio);}internal void Play(){Send("play");}internal void Pause(){Send("pause");}internal void Stop(){Send("stop");}internal void Restart(){Send("restart");}internal void Seek(int frame){Send("seek",null,frame);}
        void ClearDevice(){if(device!=null){device.Dispose();device=null;}}
        void Start(){if(source==null||source.Frames==0)return;if(State==2&&device!=null){device.Resume();Volatile.Write(ref state,1);return;}if(readFrame>=source.Frames)readFrame=baseFrame=0;if(device==null)device=simulated?(IWaveDevice)new SimulatedWaveDevice(source.Rate,Math.Min(2,source.Channels.Length)):new WinWaveDevice(source.Rate,Math.Min(2,source.Channels.Length));gain=Volume;Volatile.Write(ref state,1);}
        void Apply(Request cmd){
            if(cmd.Name=="shutdown"){closing=true;return;}
            if(cmd.Name=="source"){ClearDevice();source=cmd.Audio;readFrame=baseFrame=0;Interlocked.Exchange(ref position,0);Interlocked.Exchange(ref bytes,0);Volatile.Write(ref error,null);Volatile.Write(ref state,0);}
            else if(cmd.Name=="play")Start();
            else if(cmd.Name=="pause"){if(device!=null&&State==1){device.Pause();Volatile.Write(ref state,2);}}
            else if(cmd.Name=="stop"){ClearDevice();readFrame=baseFrame=0;Interlocked.Exchange(ref position,0);Volatile.Write(ref state,0);}
            else if(cmd.Name=="seek"||cmd.Name=="restart"){
                bool playing=State==1||cmd.Name=="restart",paused=State==2;ClearDevice();readFrame=baseFrame=source==null?0:Math.Max(0,Math.Min(source.Frames,cmd.Name=="restart"?0:cmd.Frame));Interlocked.Exchange(ref position,baseFrame);Volatile.Write(ref state,0);if(playing)Start();else if(paused)Volatile.Write(ref state,2);
            }
        }
        internal static byte[] Render(PcmAudio audio,int start,int count,ref double gain,double target){
            int channels=Math.Min(2,audio.Channels.Length);var result=new byte[count*channels*2];double step=(target-gain)/Math.Max(1,(int)(audio.Rate*.008));int ramp=Math.Min(count,Math.Max(1,(int)(audio.Rate*.008)));
            for(int i=0;i<count;i++){if(i<ramp)gain+=step;else gain=target;for(int c=0;c<channels;c++){short sample=Binary.Clamp(audio.Channels[c][start+i]*gain);int p=(i*channels+c)*2;result[p]=(byte)sample;result[p+1]=(byte)(sample>>8);}}return result;
        }
        void Run(){
            try{while(!closing){try{Request request;while(commands.TryDequeue(out request))Apply(request);if(closing)break;if(source!=null&&device!=null){if(State==1){while(device.FreeSlots>0&&readFrame<source.Frames){int count=Math.Min(2048,source.Frames-readFrame);byte[] pcm=Render(source,readFrame,count,ref gain,Volume);device.Queue(pcm);readFrame+=count;Interlocked.Add(ref bytes,pcm.Length);}if(readFrame>=source.Frames&&device.Pending==0){Interlocked.Exchange(ref position,source.Frames);ClearDevice();Volatile.Write(ref state,0);}}if(device!=null)Interlocked.Exchange(ref position,Math.Min(source.Frames,baseFrame+device.Position));}}catch(Exception){ClearDevice();Volatile.Write(ref state,0);Volatile.Write(ref error,"Audio output could not start or was disconnected. Check your speakers or headphones, then press Play.");}wake.WaitOne(8);}}finally{ClearDevice();}
        }
        public void Dispose(){if(disposed)return;Send("shutdown");disposed=true;worker.Join(3000);if(!worker.IsAlive)wake.Dispose();}
    }
}
