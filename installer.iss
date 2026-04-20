; Inno Setup installer pour Finess-for-Laure.
; Génère un .exe double-cliquable qui installe l'app dans
; %LOCALAPPDATA%\Finess-for-Laure et ajoute un raccourci menu Démarrer.
;
; Compilation (sur Windows) :
;   iscc installer.iss

#define AppName      "Finess-for-Laure"
#define AppVersion   GetEnv("APP_VERSION")
#if AppVersion == ""
  #define AppVersion "0.3.0"
#endif
#define AppPublisher "ARS"
#define AppExeName   "Finess-for-Laure.exe"

[Setup]
AppId={{2F3A4B5C-6D7E-8F90-A1B2-C3D4E5F60718}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=dist-installer
OutputBaseFilename=Finess-for-Laure-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis supplémentaires"; Flags: unchecked

[Files]
; Copie tout le dossier produit par PyInstaller (dist\Finess-for-Laure).
Source: "dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Désinstaller {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Lancer {#AppName}"; Flags: nowait postinstall skipifsilent
