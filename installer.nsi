Unicode true
!include "MUI2.nsh"
!include "x64.nsh"
Name "Radial Bridges"
OutFile "RadialBridges-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\RadialBridges"
InstallDirRegKey HKCU "Software\RadialBridges" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
VIProductVersion "1.8.0.0"
VIAddVersionKey "ProductName" "Radial Bridges"
VIAddVersionKey "FileDescription" "Radial Bridges Setup"
VIAddVersionKey "FileVersion" "1.8.0"
VIAddVersionKey "LegalCopyright" "Radial Bridges contributors"
!define MUI_ICON "payload/app.ico"
!define MUI_UNICON "payload/app.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "Install Radial Bridges for your Windows account.$\r$\n$\r$\nOpen sliced G-code, preview radial bridge paths, and inspect the result in Bambu Studio.$\r$\n$\r$\nPython is bundled. No administrator access or separate runtime installation is needed."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\RadialBridges.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open Radial Bridges"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_OK|MB_ICONSTOP "Radial Bridges requires 64-bit Windows 10 or Windows 11."
    Abort
  ${EndIf}
FunctionEnd
Section "Install"
  SetShellVarContext current
  SetOutPath "$INSTDIR"
  File /r /x "__pycache__" /x "*.pyc" "payload/*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Radial Bridges"
  CreateShortcut "$SMPROGRAMS\Radial Bridges\Radial Bridges.lnk" "$INSTDIR\RadialBridges.exe" "" "$INSTDIR\app.ico"
  CreateShortcut "$SMPROGRAMS\Radial Bridges\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\Radial Bridges.lnk" "$INSTDIR\RadialBridges.exe" "" "$INSTDIR\app.ico"
  WriteRegStr HKCU "Software\RadialBridges" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RadialBridges" "DisplayName" "Radial Bridges"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RadialBridges" "DisplayVersion" "1.8.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RadialBridges" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RadialBridges" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RadialBridges" "DisplayIcon" "$INSTDIR\RadialBridges.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RadialBridges" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RadialBridges" "NoRepair" 1
SectionEnd
Section "Uninstall"
  SetShellVarContext current
  Delete "$DESKTOP\Radial Bridges.lnk"
  RMDir /r "$SMPROGRAMS\Radial Bridges"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RadialBridges"
  DeleteRegKey HKCU "Software\RadialBridges"
  RMDir /r "$INSTDIR"
SectionEnd
