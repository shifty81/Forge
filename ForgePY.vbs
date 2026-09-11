Option Explicit
Dim shell, fso, base, app, args, cmd, py
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
app = base & "\app\ForgePYBootstrap.py"
Function Quote(value)
    Quote = Chr(34) & Replace(value, Chr(34), Chr(34) & Chr(34)) & Chr(34)
End Function
Function FindExe(name)
    Dim exec, text
    On Error Resume Next
    Set exec = shell.Exec("cmd /c where " & name & " 2>nul")
    If Err.Number <> 0 Then Err.Clear : FindExe = "" : Exit Function
    text = Trim(exec.StdOut.ReadAll)
    If InStr(text, vbCrLf) > 0 Then text = Split(text, vbCrLf)(0)
    If InStr(text, vbLf) > 0 Then text = Split(text, vbLf)(0)
    FindExe = Trim(text)
    On Error GoTo 0
End Function
py = FindExe("pythonw.exe")
If py = "" Then py = FindExe("python.exe")
If py = "" Then py = FindExe("pyw.exe") : If py <> "" Then py = Quote(py) & " -3" Else py = Quote(py)
If py = "" Then py = FindExe("py.exe") : If py <> "" Then py = Quote(py) & " -3"
If py = "" Then MsgBox "ForgePY requires Python 3.11 or newer with Tkinter.", 16, "ForgePY" : WScript.Quit 1
args = ""
Dim i
For i = 0 To WScript.Arguments.Count - 1
    args = args & " " & Quote(WScript.Arguments(i))
Next
cmd = py & " " & Quote(app) & args
shell.Run cmd, 0, False
WScript.Quit 0
