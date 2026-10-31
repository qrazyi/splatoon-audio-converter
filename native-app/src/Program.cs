using System;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Windows.Forms;

[assembly:AssemblyTitle("Splatoon Audio Converter")]
[assembly:AssemblyProduct("Splatoon Audio Converter")]
[assembly:AssemblyVersion("3.0.0.0")]
[assembly:AssemblyFileVersion("3.0.0.0")]
[assembly:InternalsVisibleTo("AudioConverter.Tests")]

namespace SplatoonAudio {
    internal static class Program {
        static bool ready;
        [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool SetDllDirectoryW(string path);
        internal static void Setup(){if(ready)return;ready=true;SetDllDirectoryW(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"_internal"));AppDomain.CurrentDomain.AssemblyResolve+=(sender,args)=>{
                if(new AssemblyName(args.Name).Name!="VGAudio")return null;
                using(var stream=typeof(Program).Assembly.GetManifestResourceStream("SplatoonAudio.VGAudio.dll")){if(stream==null)return null;var bytes=new byte[stream.Length];stream.Read(bytes,0,bytes.Length);return Assembly.Load(bytes);}
            };}
        [STAThread]static int Main(string[] args){Setup();try{return Run(args);}catch(Exception){if(Array.IndexOf(args,"--snapshot")<0)MessageBox.Show("The application could not start. Extract the complete download and make sure Windows .NET Framework 4.8 is installed.","Splatoon Audio Converter",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;}}
        [MethodImpl(MethodImplOptions.NoInlining)]static int Run(string[] args){
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);string file=null,theme=null,snapshot=null;bool verify=false;
            for(int i=0;i<args.Length;i++){if(args[i]=="--theme"&&i+1<args.Length)theme=args[++i];else if(args[i]=="--snapshot"&&i+1<args.Length)snapshot=args[++i];else if(args[i]=="--verify-playback")verify=true;else if(!args[i].StartsWith("--"))file=args[i];}
            int result=0;
            using(var form=new MainForm(theme,snapshot==null)){
                if(snapshot!=null){form.ShowInTaskbar=false;form.StartPosition=FormStartPosition.Manual;form.Location=new System.Drawing.Point(-30000,-30000);form.SnapshotPath=snapshot;form.VerifyPlayback=verify;}
                string open=file;form.Shown+=(s,e)=>{if(open!=null)form.OpenPath(open);};
                var timeout=new Timer{Interval=30000};if(snapshot!=null){timeout.Tick+=(s,e)=>{result=2;form.Close();};timeout.Start();}
                Application.Run(form);timeout.Dispose();if(form.TestFailure!=null)result=3;
            }
            InterfaceFont.Release();return result;
        }
    }
}
