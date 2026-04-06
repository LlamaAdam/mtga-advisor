' Launch MTGA Advisor without showing a console window.
' The Tkinter dashboard will appear on its own.
'
' If you want to see error output (useful for debugging), use
' "Launch MTGA Advisor.bat" instead.

Dim shell, dir
Set shell = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = dir
shell.Run "python game_advisor\main.py", 0, False
