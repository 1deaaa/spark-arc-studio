; Windows 正常安装后创建桌面入口，不注册任何开机启动项。
!macro NSIS_HOOK_POSTINSTALL
  Call CreateOrUpdateDesktopShortcut
!macroend

; 卸载时同步移除本钩子创建的桌面入口。
!macro NSIS_HOOK_PREUNINSTALL
  Delete "$DESKTOP\${PRODUCTNAME}.lnk"
!macroend
