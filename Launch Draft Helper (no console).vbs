Set objShell = CreateObject("WScript.Shell")
objShell.Run "C:\Python314\python.exe """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\main.py""", 0, False
