; Inno Setup — ورودی: dist\GoldSignal (خروجی PyInstaller). نسخه از خط فرمان: /DAppVersion=1.0.0
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
[Setup]
AppId={{B6F1D7A2-3C4E-4F7B-9A55-6E2D1C0A7F11}
AppName=طلاسنج (GoldSignal Iran)
AppVersion={#AppVersion}
DefaultDirName={autopf}\GoldSignal
DefaultGroupName=GoldSignal
OutputDir=..\Output
OutputBaseFilename=GoldSignal-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
LicenseFile=..\LICENSE

[Files]
Source: "..\dist\GoldSignal\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\طلاسنج"; Filename: "{app}\GoldSignal.exe"
Name: "{autodesktop}\طلاسنج"; Filename: "{app}\GoldSignal.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "ایجاد میان‌بر روی دسکتاپ"; Flags: unchecked

[Run]
Filename: "{app}\GoldSignal.exe"; Description: "اجرای برنامه"; Flags: nowait postinstall skipifsilent
