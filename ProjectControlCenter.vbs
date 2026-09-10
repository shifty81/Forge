Option Explicit
Dim shell, fso, base, cmd, args, i
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
args = ""
For i = 0 To WScript.Arguments.Count - 1
    args = args & " " & Chr(34) & Replace(WScript.Arguments(i), Chr(34), Chr(34) & Chr(34)) & Chr(34)
Next
cmd = "wscript.exe " & Chr(34) & base & "\Forge.vbs" & Chr(34) & args
shell.Run cmd, 0, False
