#define AppVersion "0.6.13"
[Setup]
AppId={{E67CB156-753F-48F5-943A-71157495281C}
AppName=PDFtoolkit26
AppVersion={#AppVersion}
AppPublisher=PDFtoolkit26 contributors
DefaultDirName={localappdata}\Programs\PDFtoolkit26
DefaultGroupName=PDFtoolkit26
UsePreviousAppDir=no
DisableDirPage=yes
RestartApplications=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableProgramGroupPage=yes
OutputDir=..\releases
OutputBaseFilename=PDFtoolkit26-{#AppVersion}-Setup
SetupIconFile=..\deskpdf\assets\icon.ico
UninstallDisplayIcon={app}\PDFtoolkit26.exe
Compression=lzma2
SolidCompression=yes
LicenseFile=..\LICENSE
CloseApplications=yes
ChangesAssociations=yes

[Tasks]
Name: "explorer"; Description: "Add PDFtoolkit26 tools to the PDF right-click menu"; GroupDescription: "Windows integration:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\PDFtoolkit26\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"
Source: "..\build\Shell\PDFCommand-*.dll"; DestDir: "{app}\Shell"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\build\Shell\PDFtoolkit26.ContextMenu.msix"; DestDir: "{app}\Shell"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\shell\register.ps1"; DestDir: "{app}\Shell"; Flags: ignoreversion
Source: "..\shell\unregister.ps1"; DestDir: "{app}\Shell"; Flags: ignoreversion

[InstallDelete]
; Remove obsolete bundled libraries when upgrading an existing installation.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{autodesktop}\PDFtoolkit26.lnk"; Tasks: not desktopicon

[Icons]
Name: "{group}\PDFtoolkit26"; Filename: "{app}\PDFtoolkit26.exe"
Name: "{autodesktop}\PDFtoolkit26"; Filename: "{app}\PDFtoolkit26.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Open"; Flags: deletekey; Tasks: not explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Compress"; Flags: deletekey; Tasks: not explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Extract"; Flags: deletekey; Tasks: not explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Open"; ValueType: string; ValueName: ""; ValueData: "Open with PDFtoolkit26"; Flags: uninsdeletekey; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Open"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\PDFtoolkit26.exe"",0"; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Open"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PDFtoolkit26.exe"" --shell-open ""%1"""; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Compress"; ValueType: string; ValueName: ""; ValueData: "Compress with PDFtoolkit26"; Flags: uninsdeletekey; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Compress"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\PDFtoolkit26.exe"",0"; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Compress\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PDFtoolkit26.exe"" --tool compress ""%1"""; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Extract"; ValueType: string; ValueName: ""; ValueData: "Extract pages with PDFtoolkit26"; Flags: uninsdeletekey; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Extract"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\PDFtoolkit26.exe"",0"; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFtoolkit26.Extract\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PDFtoolkit26.exe"" --tool extract ""%1"""; Tasks: explorer

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Shell\register.ps1"""; Flags: runhidden waituntilterminated; Tasks: explorer; Check: FileExists(ExpandConstant('{app}\Shell\PDFtoolkit26.ContextMenu.msix'))
Filename: "{app}\PDFtoolkit26.exe"; Description: "Open PDFtoolkit26"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\Shell"

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\Shell\unregister.ps1"""; Flags: runhidden waituntilterminated

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  PreviousName, Uninstaller: String;
  ExitCode: Integer;
begin
  Result := '';
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{E67CB156-753F-48F5-943A-71157495281C}_is1', 'DisplayName', PreviousName) and
     (Pos('DeskPDF', PreviousName) = 1) then
  begin
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{E67CB156-753F-48F5-943A-71157495281C}_is1', 'UninstallString', Uninstaller) then
    begin
      StringChangeEx(Uninstaller, '"', '', True);
      if not Exec(Uninstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
        Result := 'Could not uninstall the previous DeskPDF installation.'
      else if ExitCode <> 0 then
        Result := 'Please close DeskPDF and retry the installation.';
    end;
  end;
end;
