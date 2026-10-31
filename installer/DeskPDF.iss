#define AppVersion "0.1.0"
[Setup]
AppId={{E67CB156-753F-48F5-943A-71157495281C}
AppName=DeskPDF
AppVersion={#AppVersion}
AppPublisher=DeskPDF contributors
DefaultDirName={localappdata}\Programs\DeskPDF
DefaultGroupName=DeskPDF
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableProgramGroupPage=yes
OutputDir=..\releases
OutputBaseFilename=DeskPDF-{#AppVersion}-Setup
SetupIconFile=..\deskpdf\assets\icon.ico
UninstallDisplayIcon={app}\DeskPDF.exe
Compression=lzma2
SolidCompression=yes
LicenseFile=..\LICENSE
CloseApplications=yes
ChangesAssociations=yes

[Tasks]
Name: "explorer"; Description: "Add DeskPDF tools to the PDF right-click menu"; GroupDescription: "Windows integration:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\DeskPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"

[Icons]
Name: "{group}\DeskPDF"; Filename: "{app}\DeskPDF.exe"
Name: "{autodesktop}\DeskPDF"; Filename: "{app}\DeskPDF.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\DeskPDF.Open"; ValueType: string; ValueName: ""; ValueData: "Open in DeskPDF"; Flags: uninsdeletekey; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\DeskPDF.Open"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\DeskPDF.exe,0"; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\DeskPDF.Open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\DeskPDF.exe"" ""%1"""; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\DeskPDF.Compress"; ValueType: string; ValueName: ""; ValueData: "Compress with DeskPDF"; Flags: uninsdeletekey; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\DeskPDF.Compress"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\DeskPDF.exe,0"; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\DeskPDF.Compress\command"; ValueType: string; ValueName: ""; ValueData: """{app}\DeskPDF.exe"" --tool compress ""%1"""; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\DeskPDF.Extract"; ValueType: string; ValueName: ""; ValueData: "Extract pages with DeskPDF"; Flags: uninsdeletekey; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\DeskPDF.Extract"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\DeskPDF.exe,0"; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\DeskPDF.Extract\command"; ValueType: string; ValueName: ""; ValueData: """{app}\DeskPDF.exe"" --tool extract ""%1"""; Tasks: explorer

[Run]
Filename: "{app}\DeskPDF.exe"; Description: "Open DeskPDF"; Flags: nowait postinstall skipifsilent
