#define MyAppName "SIGA"
#define MyAppVersion "1.4.11"
#define MyAppPublisher "LGDB"
#define MyAppExeName "SIGA.exe"
#ifndef MyAppArch
  #define MyAppArch "x64"
#endif
#if MyAppArch == "x64"
  #define MySourceDir "release\\x64\\SIGA"
  #define MyAllowedArch "x64compatible"
#else
  #define MySourceDir "release\\x86\\SIGA"
  #define MyAllowedArch "x86compatible"
#endif

[Setup]
AppId={{A0C4BDA6-ECD5-49EF-BD31-77446C8491E3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\SIGA
DefaultGroupName=SIGA
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=SIGA-Setup-{#MyAppVersion}-{#MyAppArch}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed={#MyAllowedArch}
UninstallDisplayName=SIGA - Sistema de Gestión Sindical
SetupIconFile=assets\siga-app-icon.ico

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\siga-app-icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\Documentos"

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal\clr_loader\ffi\dlls\x86"
Type: files; Name: "{app}\_internal\afiliado.html"
Type: files; Name: "{app}\_internal\afiliado-manifest.json"
Type: files; Name: "{app}\_internal\manifest.json"
Type: files; Name: "{app}\_internal\sw.js"
Type: files; Name: "{app}\_internal\assets\siga-app-icon.ico"
Type: files; Name: "{app}\_internal\assets\siga-app-icon.png"

[Icons]
Name: "{autoprograms}\SIGA"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\siga-app-icon.ico"
Name: "{autodesktop}\SIGA"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\siga-app-icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir SIGA"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
#if MyAppArch == "x86"
  if IsWin64 then begin
    MsgBox('Este instalador es para Windows de 32 bits. En este equipo use el instalador SIGA x64.', mbError, MB_OK);
    Result := False;
    exit;
  end;
#endif
  Result := True;
end;
