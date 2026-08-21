#ifndef ReleaseTag
#define ReleaseTag "dev"
#endif

[Setup]
AppId={{B9B3E8D1-46F9-4A7A-BD6D-7DC0C0D6E0A1}
AppName=WaveDAQ-Launcher
AppVersion=1.0.0
AppPublisher=WaveDAQ
DefaultDirName={autopf}\WaveDAQ-Launcher
DefaultGroupName=WaveDAQ-Launcher
OutputDir=..\..
OutputBaseFilename=WaveDAQ-Launcher-windows-x64-{#ReleaseTag}-setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\WaveDAQ-Launcher.exe

[Files]
Source: "..\dist\WaveDAQ-Launcher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WaveDAQ-Launcher"; Filename: "{app}\WaveDAQ-Launcher.exe"
Name: "{autodesktop}\WaveDAQ-Launcher"; Filename: "{app}\WaveDAQ-Launcher.exe"

[Run]
Filename: "{app}\WaveDAQ-Launcher.exe"; Description: "启动 WaveDAQ-Launcher"; Flags: postinstall nowait skipifsilent
