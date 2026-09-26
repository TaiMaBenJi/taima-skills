' ===================================================================
'  DSH 破甲模式 — 静默启动器（无黑框）
'
'  用法：双击本文件即可安装；也可带参数：
'          install (默认) | check | dry-run | uninstall | list
'
'  原理：WScript.Shell.Run(cmd, 0, False) 以 SW_HIDE(0) 启动 PowerShell，
'        全程不分配可见控制台 —— 解决 .bat 双击必弹 cmd 黑框的问题。
'
'  ?? 三条血泪教训（改这个文件前必读）
'   1) 不要给 powershell.exe 再传 -WindowStyle Hidden：它会与 sh.Run 的
'      SW_HIDE 冲突，导致 PowerShell 提前退出（退出码 0 但脚本根本不执行）。
'   2) cmd 里绝不能出现非 ASCII 字节；本文件是 .vbs，中文只在注释与弹窗里。
'   3) 无窗口模式用户看不到任何过程输出 —— 所以必须给"完成/失败"弹窗，
'      否则用户不知道到底跑没跑、成没成。结果同时落盘便于排错。
'
'  与 unlock-dsh.bat 的关系：本文件是无窗口外壳，最终仍调用同一个
'  unlock-dsh.ps1，行为完全一致。
' ===================================================================
Option Explicit

Dim sh, fso, base, ps1, action, psExe, cmd, logDir, logFile, ts, resultFile, inner

Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' ---- 定位同目录下的 unlock-dsh.ps1（不依赖当前工作目录） ----
base = fso.GetParentFolderName(WScript.ScriptFullName)
ps1  = fso.BuildPath(base, "unlock-dsh.ps1")

' ---- 取参数（默认 install） ----
action = "install"
If WScript.Arguments.Count > 0 Then
  If Len(Trim(WScript.Arguments(0))) > 0 Then action = Trim(WScript.Arguments(0))
End If

' ---- 日志 ----
logDir  = sh.ExpandEnvironmentStrings("%USERPROFILE%") & "\.dsh\logs"
logFile = fso.BuildPath(logDir, "unlock-mode-launcher.log")
resultFile = fso.BuildPath(sh.ExpandEnvironmentStrings("%TEMP%"), "dsh-unlock-result.txt")

Sub LogIt(msg)
  Dim f
  On Error Resume Next
  If Not fso.FolderExists(logDir) Then fso.CreateFolder(logDir)
  Set f = fso.OpenTextFile(logFile, 8, True, -1)
  ts = Year(Now) & "-" & Right("0" & Month(Now),2) & "-" & Right("0" & Day(Now),2) & " " & _
       Right("0" & Hour(Now),2) & ":" & Right("0" & Minute(Now),2) & ":" & Right("0" & Second(Now),2)
  f.WriteLine "[" & ts & "] " & msg
  f.Close
  On Error GoTo 0
End Sub

' ---- 前置检查 ----
If Not fso.FileExists(ps1) Then
  MsgBox "找不到 unlock-dsh.ps1" & vbCrLf & vbCrLf & _
         "请确认它与本文件在同一个文件夹里：" & vbCrLf & base, _
         vbCritical, "DSH 破甲模式"
  LogIt "错误：缺少 " & ps1
  WScript.Quit 3
End If

psExe = sh.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"
If Not fso.FileExists(psExe) Then
  MsgBox "找不到 PowerShell：" & vbCrLf & psExe, vbCritical, "DSH 破甲模式"
  LogIt "错误：缺少 " & psExe
  WScript.Quit 3
End If

' ---- 组装内层 PowerShell ----
' 把 ps1 的输出全部捕获，跑完弹窗展示结果；成功/失败用不同图标。
' 刻意不加 -WindowStyle Hidden（见教训 1）。
inner = _
  "$ErrorActionPreference='Continue'; " & _
  "$out = & '" & ps1 & "' " & action & " *>&1 | Out-String; " & _
  "$code = $LASTEXITCODE; if ($null -eq $code) { $code = 0 }; " & _
  "[System.IO.File]::WriteAllText('" & resultFile & "', $out); " & _
  "Add-Type -AssemblyName System.Windows.Forms; " & _
  "$icon = if ($code -eq 0) { 'Information' } else { 'Error' }; " & _
  "$title = if ($code -eq 0) { 'DSH 破甲模式 — 完成' } else { 'DSH 破甲模式 — 失败 (exit ' + $code + ')' }; " & _
  "[System.Windows.Forms.MessageBox]::Show($out, $title, 0, " & _
  "[System.Windows.Forms.MessageBoxIcon]::$icon) | Out-Null"

' VBS 里把内层双引号转义：'...' 单引号包裹的字符串本身不含双引号，可直接用。
' 内层只用了单引号，因此这里无需转义。
cmd = """" & psExe & """ -NoLogo -NoProfile -ExecutionPolicy Bypass -Command """ & inner & """"

LogIt "静默启动 (" & action & ")"

On Error Resume Next
sh.CurrentDirectory = base
Err.Clear

' 0 = SW_HIDE（不显示窗口），False = 不等待
sh.Run cmd, 0, False

If Err.Number <> 0 Then
  MsgBox "启动失败 0x" & Hex(Err.Number) & vbCrLf & Err.Description, vbCritical, "DSH 破甲模式"
  LogIt "启动失败 0x" & Hex(Err.Number) & " - " & Err.Description
  WScript.Quit 2
End If
On Error GoTo 0

LogIt "已启动（无窗口）"
WScript.Quit 0
