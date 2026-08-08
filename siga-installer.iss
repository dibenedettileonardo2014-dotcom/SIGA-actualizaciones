#define MyAppName "SIGA"
#define MyAppVersion "1.2.18"
#define MyAppPublisher "Leonardo Di Benedetti"
#define MyAppExeName "SIGA.exe"

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
OutputBaseFilename=SIGA-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
UninstallDisplayName=SIGA - Sistema de Gestión Sindical
SetupIconFile=assets\siga-app-icon.ico

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "release\SIGA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\siga-app-icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\SIGA"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\siga-app-icon.ico"
Name: "{autodesktop}\SIGA"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\siga-app-icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir SIGA"; Flags: nowait postinstall skipifsilent
