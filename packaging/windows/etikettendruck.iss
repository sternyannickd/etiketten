; Etikettendruck – Installer für Windows (Inno Setup 6)
;
; Wird von GitHub Actions gebaut (.github/workflows/installer.yml):
;   pyinstaller --noconfirm packaging\etikettendruck.spec
;   iscc /DVersion=0.3.0 packaging\windows\etikettendruck.iss
;
; Installiert nur für den angemeldeten Benutzer, ohne Adminrechte:
;   Programm:     %LOCALAPPDATA%\Programs\Etikettendruck   (wird bei jedem Update ersetzt)
;   Eigene Daten: %LOCALAPPDATA%\Etikettendruck            (legt das Programm selbst an,
;                                                          bleibt bei Update und Deinstallation)

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{6F2B8C1E-3A4D-4E7B-9C21-5D8E0F7A1B34}
AppName=Etikettendruck
AppVersion={#Version}
AppVerName=Etikettendruck {#Version}
DefaultDirName={userpf}\Etikettendruck
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\installer
OutputBaseFilename=Etikettendruck-Installer-Windows
SetupIconFile=..\symbol.ico
UninstallDisplayIcon={app}\etikettendruck.exe
UninstallDisplayName=Etikettendruck
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=no

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopsymbol"; Description: "Symbol auf dem Desktop anlegen"; GroupDescription: "Zusätzlich:"

[InstallDelete]
; Reste einer älteren Version entfernen (nur Programmdateien, nie die eigenen Daten)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\..\dist\etikettendruck\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Etikettendruck"; Filename: "{app}\etikettendruck.exe"
Name: "{autodesktop}\Etikettendruck"; Filename: "{app}\etikettendruck.exe"; Tasks: desktopsymbol

[Run]
Filename: "{app}\etikettendruck.exe"; Description: "Etikettendruck jetzt starten"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM etikettendruck.exe"; Flags: runhidden; RunOnceId: "Beenden"

[Code]
// Ein laufendes Programm vor dem Update beenden, sonst sind die Dateien gesperrt.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Ergebnis: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM etikettendruck.exe', '', SW_HIDE,
       ewWaitUntilTerminated, Ergebnis);
  Sleep(500);
  Result := '';
end;
