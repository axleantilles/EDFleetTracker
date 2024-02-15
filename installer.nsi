
;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"
  !include "UninstallLog.nsh"

;--------------------------------
;General

  ;Name and file
  Name "Elite Dangerous Fleet Tracker"
  OutFile "installer.exe"
  Unicode True
  
  ;Default installation folder
  InstallDir "$LOCALAPPDATA\edft"

  ;Request application privileges for Windows Vista
  RequestExecutionLevel admin

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING

;--------------------------------
;Pages

  !insertmacro MUI_PAGE_LICENSE "LICENSE"
  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY
  !insertmacro MUI_PAGE_INSTFILES
  
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  
;--------------------------------
;Languages
 
  !insertmacro MUI_LANGUAGE "English"
  
; post processes
!finalize 'signtool sign /a /fd SHA256 /t http://timestamp.digicert.com %1' = 0
!uninstfinalize 'signtool sign /a /fd SHA256 /t http://timestamp.digicert.com %1' = 0
  
Section "EDFT" SecMain

  SetOutPath "$INSTDIR"
  SetRegView 64
  
  ;ADD YOUR OWN FILES HERE...
  
  ;Store installation folder
  DeleteRegKey HKCR "edft"
  DeleteRegKey HKCU "Software\edft"
  WriteRegStr HKCU "Software\edft" "" $INSTDIR
  WriteRegStr HKCR "edft" "" "URL:edft Protocol"
  WriteRegStr HKCR "edft" "URL Protocol" ""
  WriteRegStr HKCR "edft\shell\open\command" "" "$\"$INSTDIR\dist\helper.exe$\" $\"%1$\""
  File /r dist
  ;Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

SectionEnd

Section "Desktop Shortcut" SecShortcut

  CreateShortcut "$DESKTOP\EDFT.lnk" "$INSTDIR\dist\EDFT.exe"

SectionEnd

;--------------------------------
;Descriptions

  ;Language strings
  LangString DESC_SecMain ${LANG_ENGLISH} "Elite Dangerous Fleet Tracker Executable"

  ;Assign language strings to sections
  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} $(DESC_SecMain)
  !insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  ;ADD YOUR OWN FILES HERE...

  Delete "$INSTDIR\Uninstall.exe"
  
  RMDir /r "$INSTDIR\dist"
  RMDir "$INSTDIR"

  DeleteRegKey HKCU "Software\edft"
  DeleteRegKey HKCR "edft"

SectionEnd