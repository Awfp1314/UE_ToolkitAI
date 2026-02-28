Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw.exe main.py", 0, False
Set WshShell = Nothing
