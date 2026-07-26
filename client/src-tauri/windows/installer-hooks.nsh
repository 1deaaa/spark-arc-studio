; Windows 正常安装后创建桌面入口，并登记当前用户开机启动。
!macro NSIS_HOOK_POSTINSTALL
  Call CreateOrUpdateDesktopShortcut
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${PRODUCTNAME}" '$\"$INSTDIR\${MAINBINARYNAME}.exe$\"'
!macroend

; 卸载时同步移除本钩子创建的入口，不遗留失效的开机启动项。
!macro NSIS_HOOK_PREUNINSTALL
  Delete "$DESKTOP\${PRODUCTNAME}.lnk"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${PRODUCTNAME}"
!macroend
